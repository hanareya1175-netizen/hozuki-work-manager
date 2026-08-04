# Build212

## プッシュ通知機能

- 別系統の HozukiWorks Push サービスと連携する Web Push を追加。
- 管理者メニュー「通知」に「新規募集あり」一斉通知ボタンを追加。
- 管理者が任意の短文を全員へ送る「管理者からのお知らせ」を追加。
- メンバー画面に通知設定ページへのリンクを追加。
- 通常の画面遷移時には Push サービスへ通信せず、送信ボタン押下時だけ外部通信するため、Build211 の高速化を維持。
- 表示を `Ver2.0.0 Build212` に更新。

## 必要な Streamlit secrets

```toml
PUSH_SERVICE_URL = "https://<通知サービスのURL>"
PUSH_SETUP_URL = "https://<通知サービスのURL>"
PUSH_API_KEY = "<通知サービス側と同じAPIキー>"
HOZUKI_APP_URL = "https://<HozukiWorks本体のURL>"
```
