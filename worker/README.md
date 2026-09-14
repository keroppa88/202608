# 中継

ブラウザから直に叩けないものを、代わりに叩くだけのもの。2つある。

| 宛先 | 何をするか |
|---|---|
| `/`（ルート） | 相関ページの「AI分析開始」の数字を Gemini に渡し、文章を返す |
| `/jquants` | テクニカル画面の「取得」を受けて、GitHub の Actions を起こす |

どちらも計算はしない。数字の計算はページ側（`correlation.js`）で済ませてある。
株価データは `/jquants` を通らない。J-Quants の鍵は GitHub の Secrets にあり、ここには置かない。

## 配る

```sh
cd worker
npx wrangler login
npx wrangler secret put GEMINI_API_KEY      # 貼って Enter。ここ以外に鍵を置かない
npx wrangler secret put GH_TOKEN            # 個別株の取り寄せに使う。下を見る
npx wrangler secret put JQ_PASS             # 合言葉。入れなければ誰でも押せる
npx wrangler deploy
```

## 個別株の取り寄せ（`/jquants`）に要るもの

`GH_TOKEN` は GitHub の細粒度PAT。付ける権限はこのリポジトリの **Contents: 読み書き** だけ。
これで `repository_dispatch` を投げられる。中身の読み書きはしない。

`JQ_PASS` を入れると、画面の「合言葉」が一致したときだけ通す。入れなければ送り元だけ見る。
サイトは公開なので、`ALLOWED_ORIGINS` は curl では偽装できる。誰かに Actions を
回されて困るなら入れる。

配ると `https://soba-ai.<アカウント名>.workers.dev` のような宛先が出る。
その宛先を `index.html` の

```js
const AI_ENDPOINT = "";
```

に書く。書くまでは、押しても送らずにその旨が出る。

## 直したいとき

| どこ | 何 |
|---|---|
| `wrangler.toml` の `GEMINI_MODEL` | 使うモデル |
| `wrangler.toml` の `ALLOWED_ORIGINS` | 受け付ける送り元。カンマ区切り |
| `index.js` の `RATE_LIMIT` | 1分あたりの回数 |
| `index.js` の `RULES` | 相関だけを渡したときのAIへの指示 |
| `index.js` の `TECH_RULES` | テクニカル＋相関を渡したときのAIへの指示 |

直したら `npx wrangler deploy` をもう一度。1ファイルなので、
ダッシュボードの Edit code に `index.js` を貼っても上がる。

`TECH_RULES` はページからも使う。サイトの「AI分析用テキスト出力」は
`GET /prompt` でこの文面を読み、落とす .txt の頭に付ける。文面はここに
1つしか無いので、直せば両方に効く。

## 動きを見る

```sh
npx wrangler tail
```

失敗したときは、その内容がそのままページのコメント欄に出る。

## 定時更新をCloudflareから起動する

`soba-ai` の Cron Trigger が10分ごとに動き、既存の時刻表に該当する場合だけ
`repository_dispatch` を送る。取得・CSV保存・公開は従来どおりGitHubで実行する。
`GH_TOKEN` は既存の Contents: 読み書き権限を利用し、追加のActions権限は不要。
HTTP 204は起動要求の受理であり、処理開始・完了の保証ではない。
GitHubランナーの待ち時間は残る。

| 日本時間 | 曜日 | 対象 |
|---|---|---|
| 07:00 | 火〜土 | Fear & Greed、松井証券、金利 |
| 08:00 | 火〜土 | 米国株記事 |
| 08:10 | 火〜土 | 海外相場 |
| 09:10 | 火〜土 | 暗号資産 |
| 18:00 | 月〜金 | 日本株、JPX、日経指数、国内記事・指標・ランキング、読売333 |
| 18:20 | 月〜金 | 商品・先物 |
| 18:30 | 月〜金 | 個別株コピー、比率算出 |

### 有効化

1. この変更をGitHubのmainへ反映する。`repository_dispatch`はmain上の定義を使う。
2. `cd worker && npx wrangler deploy`。既存のWorkerと秘密情報をそのまま使う。
   初期状態は `SCHEDULE_ENABLED = "false"` なので、起動命令は送らない。
3. CloudflareのCron設定の反映を待つ（最大15分）。WorkerのログでCron呼び出しを確認する。
4. 更新予定時刻を避けて切り替える。GitHubの Settings → Secrets and variables →
   Actions → Variables に `CLOUDFLARE_SCHEDULE` = `true` を設定する。
   これでGitHub由来のscheduleジョブだけがスキップされる。Run workflowは使える。
5. `wrangler.toml` の `SCHEDULE_ENABLED` を `"true"` に変え、再度deployする。
   この設定変更もリポジトリへ保存する。
6. 次の設定時刻にCloudflareログの `dispatch accepted`、GitHubの
   `repository_dispatch` 実行、取得ステップ、CSV更新、ページ公開を確認する。

受理不明時の重複起動を避けるため、Workerは自動再送しない。
送信失敗はCron実行をエラーにする。他の対象への送信は継続する。
GitHubとCloudflareの両スケジューラーを同時に有効化しないこと。
復旧する場合はWorkerをfalseに戻してから、GitHub変数をfalseに戻す。

検証: `node --test worker/schedule.test.mjs`
