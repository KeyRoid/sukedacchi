# スケだっち☆

Google カレンダーの予定をもとに、クライアント向けのメール文を自動生成するアプリです。

## セットアップ方法（開発者向け）

1. このリポジトリをクローンする  
2. `sample.env` を `.env` にリネームし、クライアントIDとシークレットを入力  
3. 必要なライブラリをインストール  
4. アプリを起動  

## 注意事項

- `.env`、`token.json`、`templates.db` などは `.gitignore` で除外済み  
- OAuth スコープは `calendar.readonly` のみを使用
