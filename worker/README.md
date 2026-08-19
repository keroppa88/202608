# AI分析の中継

相関ページの「AI分析開始」から送られてきた数字を Gemini に渡し、返ってきた文章を返すだけのもの。

数字の計算はページ側（`correlation.js`）で済ませてある。ここは計算しない。

## 配る

```sh
cd worker
npx wrangler login
npx wrangler secret put GEMINI_API_KEY      # 貼って Enter。ここ以外に鍵を置かない
npx wrangler deploy
```

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
