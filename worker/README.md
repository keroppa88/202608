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
| `index.js` の `RULES` | AIへの指示 |

直したら `npx wrangler deploy` をもう一度。

## 動きを見る

```sh
npx wrangler tail
```

失敗したときは、その内容がそのままページのコメント欄に出る。
