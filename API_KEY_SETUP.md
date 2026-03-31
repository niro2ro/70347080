# API キー設定ガイド

Hiro.exe は Anthropic Claude API を使用しています。使用開始前に API キーを設定してください。

---

## 🔑 API キーの取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. ログイン（アカウント作成が必要な場合）
3. **API Keys** → **Create Key** をクリック
4. API キー（`sk-ant-...` で始まる文字列）をコピー

---

## ⚙️ 設定方法

API キー設定の優先順位：

```
1. Streamlit Secrets  （本番環境推奨）
    ↓
2. .env ファイル      （開発環境推奨）
    ↓
3. 未設定             （エラー）
```

### 方法 1️⃣：Streamlit Secrets（本番環境・Streamlit Cloud）

**Streamlit Cloud デプロイ時：**

1. [Streamlit Cloud](https://share.streamlit.io/) で アプリを選択
2. **Settings** → **Secrets** をクリック
3. 以下をコピー＆ペースト：

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

4. API キーを記入して保存
5. アプリが自動で再起動

**ローカル環境で テスト：**

```bash
# 1. .streamlit/secrets.toml を作成
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# 2. API キーを編集
# エディタで ANTHROPIC_API_KEY の値を設定

# 3. Streamlit 起動
streamlit run app.py
```

⚠️ `.streamlit/secrets.toml` は `.gitignore` に追加済み（git にアップロードされません）

---

### 方法 2️⃣：.env ファイル（開発環境）

**ローカル開発環境での推奨方法：**

```bash
# 1. .env ファイルを作成
cp .env.example .env

# 2. エディタで API キーを記入
# ANTHROPIC_API_KEY=sk-ant-...

# 3. Streamlit 起動
streamlit run app.py
```

⚠️ `.env` ファイルは `.gitignore` に追加済み（git にアップロードされません）

---

## ✅ 動作確認

アプリを起動して以下を確認：

```
streamlit run app.py
```

1. **ログイン画面**が表示される → 正常
2. **メイン画面**の各機能で **「AI質問」が利用可能** → API キー設定済み
3. **エラーメッセージ表示** → API キー未設定（上記を再確認）

---

## 🔒 セキュリティ注意事項

- API キーは **絶対に公開リポジトリにコミットしない**
- `.env` と `.streamlit/secrets.toml` は `.gitignore` に記載済み
- GitHub/GitLab にプッシュする前に `git status` で確認
- 誤ってアップロードした場合：
  - Anthropic Console で キーを **Revoke（無効化）** → 新規発行

---

## 💳 料金について

- **無料試用版**：$5 初期クレジット
- **従量課金**：使用量に応じて請求（API レファレンス参照）
- **モニタリング**：Anthropic Console → Usage でいつでも確認可能

---

## 🆘 トラブルシューティング

### ❌ エラー：「APIキーが設定されていません」

```
→ 以下を確認：
  1. .env または .streamlit/secrets.toml が存在するか
  2. ANTHROPIC_API_KEY の値が記入されているか
  3. API キーが有効か（Console で確認）
```

### ❌ エラー：「APIキーが無効です」

```
→ 原因：
  1. Anthropic でキーを Revoke した
  2. キー文字列が不完全（コピペミス）

→ 対処：
  - Anthropic Console で新規キーを発行
  - .env または secrets.toml を再設定
```

### ❌ エラー：「レート制限に達しました」

```
→ API 呼び出し頻度が上限を超えた
→ 少し待ってから再試行
→ 本番運用時は キャッシュ TTL を確認
```

---

## 📚 参考リンク

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude API Reference](https://docs.anthropic.com/claude/reference/)
- [Streamlit Secrets Management](https://docs.streamlit.io/deploy/streamlit-cloud/deploy-your-app/secrets-management)

---

**設定完了後、アプリを再起動してください。**

```bash
streamlit run app.py
```
