# HozukiWorks Ver2.0.0 — Neon接続

1. Streamlit Community Cloud のアプリ管理画面で Settings → Secrets を開く。
2. 次の形式で、Neonの接続文字列を登録する。

```toml
DATABASE_URL = "postgresql://..."
```

3. Save後、アプリを再起動する。
4. 初回接続時、Neonが空なら `data` フォルダのCSVを自動移行する。
5. 管理者メニュー「データ管理」で保存先が `Neon PostgreSQL` と表示されることを確認する。

注意: 接続文字列はGitHub、チャット、スクリーンショットへ載せない。
