# H-11 v3 — GMO API Key/Secret の Keychain 登録手順書（no-POST・operator専任）

Date: 2026-07-11

Status: **REGISTERED_AND_VERIFIED（2026-07-11）**（operatorが方法B・ターミナルCLIで登録完了。
方法Aの新macOS「パスワード」アプリ新規パスワード機能は`security find-generic-password`から
読み取り不可だったため使用しなかった。検証結果: api_key length=32 / api_secret length=64・
値は非表示）

対応する読み取りコード: `backend/app/services/h11_v3_keychain_credential_no_post.py`
（`read_h11_v3_keychain_secret(service=..., account=...)`）

## 0. 前提

- GMOコインの外国為替FX API設定で、**APIキー**と**APIシークレット**が発行済みであること
  （未発行の場合は会員ページ → 外国為替FX → API設定 → 「APIキーを新規追加」から発行）
- APIシークレットは発行時にしか表示されないため、発行直後にこの手順で登録すること
- 発行時に**発注権限**を有効にするか、[account確認チェックリスト](H11_V3_ACCOUNT_CHECK_CHECKLIST_NO_POST_20260711.md)
  の方針に沿って決めること（照会のみ権限では発注できない）

## 1. 命名規則（固定・変更しないこと）

読み取りコードがこの service/account の組み合わせを前提にする。

| 項目 | service | account | 値 |
|---|---|---|---|
| APIキー | `h11_v3_gmo_fx_api_key` | `h11_v3` | GMO APIキー本体 |
| APIシークレット | `h11_v3_gmo_fx_api_secret` | `h11_v3` | GMO APIシークレット本体 |

`h11_v3_test_only_` で始まる service 名はテスト専用（`h11_v3_test_only_ephemeral` 等）で、
このガイドの登録先とは別物。誤って test 用 helper（`write_h11_v3_keychain_secret_for_test_only`）
を実credentialの登録に使わないこと（`h11_v3_test_only_` 以外の service 名は helper 側で拒否される
ため、そもそも実行不能）。

## 2. 登録方法A: キーチェーンアクセス.app（GUI）

**注意（2026-07-11実績）**: 新macOSの「パスワード」アプリ（Spotlightで見つかりやすい別アプリ）の
「新規パスワード」機能で作成した項目は、`security find-generic-password`から読み取り不可だった
（Internet Password形式等、Generic Password以外の形式で保存されると推測される）。
**「パスワード」アプリではなく、必ず「キーチェーンアクセス」アプリを使うこと。**
見つからない・不安な場合は「3. 登録方法B」のターミナルCLIを使う方が確実。

1. Spotlight（`⌘+Space`）で「キーチェーンアクセス」を開く
2. 左上のキーチェーンで「**ログイン**」を選択（システムキーチェーンではない）
3. メニュー「ファイル」→「新規パスワード項目...」
4. ダイアログで以下を入力し、APIキーを登録:
   - 項目名: `h11_v3_gmo_fx_api_key`
   - アカウント名: `h11_v3`
   - パスワード: GMO APIキーの値を貼り付け
   - 「追加」をクリック
5. 同様の手順でAPIシークレットも登録:
   - 項目名: `h11_v3_gmo_fx_api_secret`
   - アカウント名: `h11_v3`
   - パスワード: GMO APIシークレットの値を貼り付け
6. 登録した2項目をダブルクリックし、「アクセス制御」タブで以下を確認:
   - 「このアイテムへのアクセスを許可するアプリケーションを確認する」を選択したままにする
     （常時許可にすると無条件でアクセス可能になるため非推奨）
   - 初回読み取り時にTerminal/Pythonへのアクセス許可ダイアログが出たら、
     実行に使うアプリ（Terminal.app等）を選び「常に許可」ではなく「許可」を選ぶことを推奨
     （日次runのたびにダイアログが出るのが煩わしい場合のみ「常に許可」を検討）

## 3. 登録方法B: ターミナル（`security` コマンド）

APIキーの登録:

```bash
security add-generic-password \
  -s h11_v3_gmo_fx_api_key \
  -a h11_v3 \
  -w '<ここにAPIキーを貼り付け>' \
  -U
```

APIシークレットの登録:

```bash
security add-generic-password \
  -s h11_v3_gmo_fx_api_secret \
  -a h11_v3 \
  -w '<ここにAPIシークレットを貼り付け>' \
  -U
```

**注意**:
- `-U` は既存項目があれば更新（upsert）する意味。ローテーション時もこのコマンドを再実行すればよい
- コマンドをそのままシェル履歴に残したくない場合、コマンドの先頭に半角スペースを1つ入れて実行すると
  多くのシェル設定（`HIST_IGNORE_SPACE`等）で履歴から除外される。または実行後に
  `history -d <行番号>` で該当行を削除する
- ターミナルの操作ログ・スクリーンショット・このチャットに値を貼り付けないこと

## 4. 登録後の検証（値を一切表示しない）

以下のPythonスニペットは**登録できているかどうかのbooleanだけ**を表示し、値は一切出力しない。

```bash
cd backend
.venv/bin/python -c "
from app.services.h11_v3_keychain_credential_no_post import read_h11_v3_keychain_secret, H11V3KeychainError
for label, service in [('api_key', 'h11_v3_gmo_fx_api_key'), ('api_secret', 'h11_v3_gmo_fx_api_secret')]:
    try:
        secret = read_h11_v3_keychain_secret(service=service, account='h11_v3')
        length = len(secret.reveal_once())
        print(f'{label}: OK (length={length})')
    except H11V3KeychainError as e:
        print(f'{label}: NOT_FOUND_OR_ERROR ({e})')
"
```

出力は `api_key: OK (length=NN)` のように、**文字数だけ**を表示する（値そのものは出さない）。
`NOT_FOUND_OR_ERROR` が出た場合は、service/account名の打ち間違いか未登録。

## 5. 削除・ローテーション

削除（GUIならキーチェーンアクセスで項目を選び`⌘+Delete`）:

```bash
security delete-generic-password -s h11_v3_gmo_fx_api_key -a h11_v3
security delete-generic-password -s h11_v3_gmo_fx_api_secret -a h11_v3
```

ローテーション（GMO側でキー再発行後）は、削除せず「2. 登録方法A」または「3. 登録方法B」を
同じ service/account 名で再実行すればよい（上書きされる）。

## 6. この先の実装（別Step・現時点では未着手）

このガイドでKeychainに値が入っても、それだけでは何も自動化されない。現状:

- 実sender（IFDOCO送信・メール送信）は disabled のまま（`docs/H11_V3_ACTUAL_ACTIVATION_OPERATOR_DECISION_SHEET_NO_POST_20260711.md`参照）
- Keychainから読んだ`H11V3SealedSecret`を実際にGMO APIの署名生成へ渡す配線は、
  `H11V3_ACTUAL_ACTIVATION_STEP`の中でのみ実装する
- 本ガイドはあくまで「credentialの保管場所を安全に準備する」ためのものであり、
  actual POST許可やStage移行を意味しない

```text
credential_registration_guide_only=true
actual_post=false
credential_read_by_ai=false
value_displayed_in_this_document=false
```
