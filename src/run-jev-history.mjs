import fs from 'node:fs';
import path from 'node:path';
import { gzipSync } from 'node:zlib';
import { ROOT, TARGETS, MODEL, VERSION, IMPLEMENTATION_HASH, hash, loadMarket, weeks, lastFriday, makePayload, aggregate, workerApi, outcome, DAYS } from './jev-history.mjs';

const args=process.argv.slice(2);
const option=(name,fallback)=>{const i=args.indexOf('--'+name);return i<0?fallback:args[i+1];};
const mode=option('mode','prepare');
if(!['prepare','pilot','backfill','update','aggregate'].includes(mode)) throw Error('Unknown mode');
const transport=option('transport','worker');
if(!['worker','direct'].includes(transport)) throw Error('Unknown transport');
const end=option('end',lastFriday());
if(!/^\d{4}-\d{2}-\d{2}$/.test(end) || new Date(end+'T00:00:00Z').getUTCDay()!==5 || end>lastFriday()) throw Error('end must be a completed Friday');
const limit=Number(option('limit',mode==='pilot'?'12':mode==='update'?'6':'2000'));
if(!Number.isInteger(limit)||limit<1||limit>2000) throw Error('limit must be 1..2000');
const output=path.join(ROOT,'data/jev',VERSION);
fs.mkdirSync(output,{recursive:true});
const summaryPath=path.join(output,'summary.json');
if(fs.existsSync(summaryPath)) {
  const previous=JSON.parse(fs.readFileSync(summaryPath,'utf8'));
  if(previous.implementationHash && previous.implementationHash!==IMPLEMENTATION_HASH) throw Error('Calculation code changed: increment VERSION before making new judgments');
}
const save=(file,value)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.tmp',JSON.stringify(value,null,2)+'\n');fs.renameSync(file+'.tmp',file);};
const market=await loadMarket();
console.log(JSON.stringify({version:VERSION,mode,end,series:Object.fromEntries(TARGETS.map(t=>[t.name,{n:market[t.key].length,last:market[t.key].at(-1)?.d}]))}));
const cutoffs=weeks(end);
const tasks=(mode==='pilot'?[cutoffs[0],cutoffs.at(-1)]:[...cutoffs].reverse()).flatMap(cutoff=>TARGETS.map(target=>({target,cutoff})));
const records=[];
for(const t of TARGETS){const dir=path.join(output,t.id);if(fs.existsSync(dir)) for(const file of fs.readdirSync(dir).filter(n=>/^\d{4}-\d{2}-\d{2}\.json$/.test(n))) records.push(JSON.parse(fs.readFileSync(path.join(dir,file),'utf8')));}
let calls=0, tokens=0, failure=null;
try {
  for(const {target,cutoff} of tasks) {
    if(mode==='aggregate'||calls>=limit) break;
    const file=path.join(output,target.id,cutoff+'.json');
    if(fs.existsSync(file)) continue;
    const start=performance.now();
    const payload=makePayload(market,target,cutoff);
    const request=workerApi.buildJevRequest(payload,MODEL);
    const bytes=Buffer.byteLength(JSON.stringify(payload));
    if(bytes>96*1024) throw Error('Payload exceeds Worker limit');
    if(mode==='prepare') { console.log(JSON.stringify({target:target.id,cutoff,bytes,questions:Object.keys(request.questions).length,buildMs:Math.round(performance.now()-start)})); calls++; continue; }
    fs.mkdirSync(path.dirname(file),{recursive:true});
    fs.writeFileSync(file+'.input.json.gz',gzipSync(JSON.stringify(request)));
    let response;
    if(transport==='direct') {
      if(!process.env.TYPESAFE_API_KEY) throw Error('TYPESAFE_API_KEY missing');
      const res=await fetch('https://api.typesafe.ai/v1/systemone',{method:'POST',redirect:'error',signal:AbortSignal.timeout(60000),headers:{'content-type':'application/json',authorization:`Bearer ${process.env.TYPESAFE_API_KEY}`},body:JSON.stringify(request)});
      const raw=await res.text();
      // 認証ヘッダーを保存しない。元応答はAPIから受信した本文のみ。
      fs.writeFileSync(file+'.response.txt',raw.split(process.env.TYPESAFE_API_KEY).join('[REDACTED]'));
      if(!res.ok) throw Error(`Jev HTTP ${res.status} at ${target.id}/${cutoff}`);
      const json=JSON.parse(raw);
      const horizons=workerApi.parseJevAnalysis(json,request);
      response={provider:'jev',model:json.model,usage:json.usage,horizons,text:workerApi.formatJevAnalysis(payload,horizons)};
    } else {
      // 既存WorkerのSecretを使用する。GitHubへAPIキーを複製しない。
      const res=await fetch('https://soba-ai.kaikai9984.workers.dev/jev',{method:'POST',redirect:'error',signal:AbortSignal.timeout(65000),headers:{'content-type':'application/json',origin:'https://keroppa88.github.io'},body:JSON.stringify(payload)});
      const raw=await res.text();fs.writeFileSync(file+'.response.txt',raw);
      if(!res.ok) throw Error(`Worker HTTP ${res.status} at ${target.id}/${cutoff}`);
      response=JSON.parse(raw);
    }
    if(response.provider!=='jev'||response.model!==MODEL||!Number.isSafeInteger(response.usage?.input_tokens)||response.usage.input_tokens<0||!Array.isArray(response.horizons)||response.horizons.length!==3||response.horizons.some(h=>!['ok','insufficient'].includes(h.status)||h.status==='ok'&&!(typeof h.score==='number'&&h.score>=0&&h.score<=100))) throw Error('Invalid/version-mismatched Jev response');
    const record={version:VERSION,target:target.id,cutoff,asOf:payload.asOf,requestHash:hash(request),createdAt:new Date().toISOString(),response};
    save(file,record); records.push(record);calls++;tokens+=response.usage.input_tokens;
    console.log(JSON.stringify({call:calls,target:target.id,cutoff,scores:response.horizons.map(h=>h.score),inputTokens:response.usage.input_tokens,costYen:response.usage.input_tokens*.042/1e6*155,elapsedMs:Math.round(performance.now()-start)}));
    if(transport==='worker') await new Promise(resolve=>setTimeout(resolve,11000));
  }
} catch(error) {failure=String(error.message);console.error(failure);process.exitCode=1;}
if(mode!=='prepare') {
  const current=records.filter(r=>r.cutoff>=cutoffs[0]&&r.cutoff<=end);
  const summary={version:VERSION,implementationHash:IMPLEMENTATION_HASH,model:MODEL,generatedAt:new Date().toISOString(),from:cutoffs[0],through:end,expected:cutoffs.length*6,completed:current.length,
    methodology:{entry:'翌週最初の取引日の始値',maxRise:'期間内高値と購入価格の比率。最低0%',maxLoss:'期間内安値と購入価格の比率。最大0%',closeDrawdown:'購入価格から始めた終値系列の最大ドローダウン',sample:'毎週末。重複期間を含み、独立した試行ではない',insufficientBelow:20,comparison:'対象以外の5指数＋ドル円＋日米10年債利回り。固定8比較',data:'現在保存されている過去価格を使用。データ改訂・モデルの学習内容による影響を分離した検証ではない'},
    totalInputTokens:current.reduce((n,r)=>n+r.response.usage.input_tokens,0),targets:aggregate(current,market),
    latest:Object.fromEntries(TARGETS.map(t=>[t.id,current.filter(r=>r.target===t.id).sort((a,b)=>b.cutoff.localeCompare(a.cutoff))[0]||null]))};
  save(path.join(output,'summary.json'),summary);
  save(path.join(output,'outcomes.json'),current.map(r=>({target:r.target,cutoff:r.cutoff,periods:Object.fromEntries(DAYS.map(n=>[n,outcome(market[TARGETS.find(t=>t.id===r.target).key],r.cutoff,n)]))})));
  save(path.join(ROOT,'data/jev/manifest.json'),{version:VERSION,summary:`data/jev/${VERSION}/summary.json`,updatedAt:summary.generatedAt});
  save(path.join(output,'last-run.json'),{mode,calls,inputTokens:tokens,estimatedUsd:tokens*.042/1e6,estimatedYenAt155:tokens*.042/1e6*155,failure});
}
