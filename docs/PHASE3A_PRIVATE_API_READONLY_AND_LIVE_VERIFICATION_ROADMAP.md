# Phase 3A準備: Private API read-only / Live Verification / 実資金検証ロードマップ設計

本書は、FX Strategy Labが将来Private API read-only確認、Live Verification Mode、極小実資金検証へ進む場合の
ロードマップを安全に定義するための設計docsである。

今回は **設計のみ** であり、Private API接続、APIキー入力・表示・保存、`.env`表示・変更、broker実装、
注文API実装、実注文、実資金検証、コード修正、テスト追加、本番公開API追加には進まない。

## 1. 目的

- Phase 3A〜3Dの段階的な安全ロードマップを定義する。
- Private API read-onlyの対象と禁止境界を明確にする。
- APIキー / secret管理の原則を、実装前に文書化する。
- Live Verification Modeと極小実資金検証の前提条件を整理する。
- Phase 2E-5 / Phase 2F / Phase 2GのPublic shadow確認が完了するまで、Private API実装や実注文へ進まない理由を明文化する。

## 2. 現在地

現時点で完了していること:

- Phase 2E-5短期3回確認レビューで、3回すべての `REAL_PUBLIC_BID_ASK` を確認済み。
- 3回合計でcandidate 5件、`ALLOW_SHADOW` 3件、`REJECT_SHADOW` 2件を確認済み。
- ALLOW時のみvirtual resultが生成され、REJECT時にはvirtual resultが生成されないことを確認済み。
- ticker/kline skewは `NO_TRADE` へ安全に倒れた。
- safety violation、broken/skipped、invalid risk rowは0。
- raw response保存なし。
- Private API、APIキー、broker、実注文、実資金は未使用。
- Phase 2G Public shadow risk/auditオフライン最終デバッグ監査は完了。既存テスト、focused test、
  offline mock run、summarize、禁止参照確認により、判定は
  **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**。
- Phase 3B-0 Private API read-only公式仕様確認・実装設計は完了。GMOコイン外国為替FXの公式API docsに基づき、
  REST GETのread-only候補、POSTの注文・変更・取消・決済系禁止endpoint、認証・署名、APIキー / secret管理、
  Phase 3B分割案を整理した。
- Phase 3B-1 mocked private readonly skeletonは完了。実接続なし・APIキー環境読込なし・`.env`読込なしの
  read-only skeleton、auth/signing helper、sanitized schemas、errors、forbidden endpoint guard、
  mocked tests、no-order-import guardを追加した。
- Phase 3B-2 mocked private readonly endpoints拡張は完了。GET read-only候補7件のmocked tests、
  sanitizer、sanitized error handling、forbidden endpoint guard拡張を追加した。実接続、APIキー入力、
  `.env`読込・変更、broker、注文API、実注文は未実施。
- Phase 3B-3 private readonly preconnect reviewは完了。APIキー / secret管理、read-only権限分離、
  `.env`安全手順、Phase 3B-4初回接続endpoint、禁止endpoint、接続前後チェックリスト、停止条件を
  docs化した。判定はAだが、実接続、APIキー入力、`.env`変更、broker、注文API、実注文は未実施。
- Phase 3B-4 Private API read-onlyローカル接続確認は総合レビューまで完了。`account/assets`、
  `openPositions`、`activeOrders` は最終successで、raw response、headers、signature、credentialsの
  保存・表示なし、broker、OrderRequest、注文API、実注文、実資金検証なしを確認した。

Phase 3B以降で未完了のこと:

- Phase 2F Public shadow risk/audit安定性レビュー、Phase 2Gオフライン最終デバッグ監査、Phase 3B-0、
  Phase 3B-1、Phase 3B-2、Phase 3B-3、Phase 3B-4は完了した。ただし、注文API、broker、OrderRequest、
  実注文は未実施。
- Live Verification Mode、注文API、実資金検証は未実施。

## 3. Phase 3A〜3Dロードマップ

### Phase 3A: Private API read-only準備設計

本書の対象である。やることは設計のみ。

- Private API read-onlyで何を見てよいかを定義する。
- APIキー / secret管理方針を定義する。
- read-only境界と禁止APIを定義する。
- Phase 3Bへ進む条件を定義する。
- Live Verification Modeと極小実資金検証までの距離感を定義する。

Phase 3Aでは実装、接続、キー設定、`.env`変更、注文API、broker送信は行わない。

### Phase 3B: Private API read-only実装・接続確認

Phase 3Aレビュー、Phase 2E-5短期確認、Phase 2Fレビュー、Phase 2G監査、Phase 3B-0公式仕様確認を
通過した後に、別タスクで扱う。Phase 3B-1 mocked skeleton、Phase 3B-2 endpoint拡張、
Phase 3B-3 preconnect review、Phase 3B-4 read-onlyローカル接続確認は完了済みである。

Phase 3Bで扱ってよい候補:

- 残高照会。
- 証拠金 / 余力照会。
- 建玉照会。
- 注文一覧 / 注文履歴照会。
- 約定履歴照会。
- 取引余力やレバレッジ関連の参照。

Phase 3Bでも扱わないもの:

- 新規注文。
- 注文変更。
- 注文取消。
- 建玉決済。
- broker送信関数。
- 自動売買。
- 実資金検証。

API endpoint名はPhase 3B-0で公式docsを確認済みである。実装時はPhase 3B-0のread-only候補と禁止endpointを
再確認し、read-only照会だけに限定する。

### Phase 3C: Live Verification Mode設計

将来フェーズ。Private API read-onlyが安全に確認できた後、実注文前に独立して設計レビューする。

目的:

- 実注文を行う前の最終安全モードを設計する。
- 注文意図、残高、建玉、注文履歴、risk decision、kill switch、ユーザー明示承認を1つのチェックリストで束ねる。
- 100通貨単位・1回だけ・手動のみの検証へ進めるかを判断する。

Phase 3Cでは、まだ実注文しない。

### Phase 3D: 極小実資金検証

将来フェーズ。Phase 2E-5、Phase 2F、Phase 3A、Phase 3B、Phase 3Cをすべて通過した後に、明示承認がある場合だけ検討する。

初期条件案:

```text
symbol = USD_JPY
units = 100
orders_count = 1
execution = manual only
frequency = one-time verification
max_open_positions = 1
auto_retry = false
auto_reentry = false
schedule / cron / bot = false
```

Phase 3Dは自動売買開始ではない。極小の実注文疎通を1回だけ確認するための検証であり、収益性評価ではない。

## 4. Private API read-only設計

read-onlyで参照してよい候補:

- 口座残高。
- 証拠金維持率、必要証拠金、余力。
- 建玉一覧。
- 未約定注文一覧。
- 注文履歴。
- 約定履歴。
- 取引余力、取引可能数量、レバレッジ関連の参照情報。

設計原則:

- 公式仕様でread-only照会であることを確認してから実装する。
- HTTP method、endpoint、権限種別を実装前レビューで明記する。
- raw response、headers、署名素材、credentialを保存しない。
- responseは必要最小限に正規化し、ログにはsecretや個人情報を出さない。
- 本番公開API、frontend、reports公開へ直結しない。

## 5. APIキー / secret管理方針

Phase 3AではAPIキーを扱わない。ユーザーにAPIキーを入力・貼り付け・表示させない。

将来Phase 3B以降で必要になる場合の原則:

- APIキー / secretはChatGPT、Codex、Claude Code、GitHub、docs、commit、ログに貼らない。
- `.env`は読まない、表示しない、commitしない。
- `.env.example`に実値を書かない。今回も変更しない。
- OS環境変数またはlocal-only `.env`を使う場合も、別タスクで明示承認後に限定する。
- providerが権限分離を提供する場合は、read-onlyキーとorder可能キーを分ける。
- Phase 3Bではread-only権限だけを使い、order権限は有効化しない。
- キーのローテーション、失効、漏洩時停止手順を事前に決める。
- request headers、署名対象文字列、raw payload、エラー詳細にsecretが混入しないようにする。

secret漏洩を疑う条件:

- Git diff、staged diff、logs、summary、JSONL、reports、terminal outputにキーらしき文字列が出る。
- `.env`がtracking対象になる。
- raw responseやheadersが保存される。

この場合はPhase 3B以降を止め、実装・運用レビューへ戻る。

## 6. read-only境界

read-onlyとして扱えるもの:

```text
GET / inquiry / list / history / status
balance inquiry
margin inquiry
position inquiry
open order inquiry
order history inquiry
execution history inquiry
account status inquiry
```

禁止するもの:

```text
new order
market order
limit order
stop order
close position
amend order
cancel order
bulk cancel
leverage change
account setting change
fund transfer
broker submit/send/place/cancel/amend
OrderCandidate -> OrderRequest conversion
```

コード境界案:

- read-only clientは将来作る場合も、注文系methodを持たない。
- 注文系endpointのURL、payload builder、broker adapterをPhase 3Bに含めない。
- `backend/app/main_readonly.py`には追加しない。
- frontendには表示しない。
- local CLIを作る場合も、1回実行・照会のみ・raw response保存なしに限定する。

## 7. Phase 3Bへ進む条件

Phase 3Bに進む前に最低限満たす条件:

```text
Phase 2E-5短期確認で少なくとも2回以上の安全runを確認
Phase 2E-5短期3回の完了、または未完了理由が安全に説明済み
Phase 2F Public shadow risk/audit安定性レビュー完了
Phase 2G Public shadow risk/auditオフライン最終デバッグ監査完了
Phase 3B-0 Private API read-only公式仕様確認・実装設計完了
safety violation 0
broken/skipped 0
invalid_risk_row_count 0
raw_response_saved=false 維持
Private API / APIキー / broker / 実注文なしをPhase 2Eで維持
Phase 3A設計レビュー完了
read-only endpointと禁止endpointの整理完了
APIキー / secret管理手順のレビュー完了
実装対象がread-only照会に限定されている
backend公開API / frontend / main_readonly変更なしの方針が維持されている
```

Phase 3Bへ進まない条件:

- Phase 2E-5 / Phase 2Fでsafety violation、summary破損、raw response保存、相関不整合が出ている。
- APIキー管理手順が未整理。
- read-only権限と注文権限を分けられない、または権限範囲が不明。
- 実装範囲に注文、変更、取消、broker送信が混入している。

## 8. Live Verification Mode設計

Live Verification Modeは、極小実資金検証の直前に置く安全モードである。

最小仕様案:

- manual only。
- 100通貨単位固定。
- 1回だけ。
- `USD_JPY`のみ。
- 最大建玉1。
- 未約定注文がある場合は停止。
- 既存建玉がある場合は停止。
- kill switchがactiveなら停止。
- safety violationが1件でもあれば停止。
- risk decisionが `ALLOW_SHADOW` 相当でなければ停止。
- candidate、risk decision、order intentのID相関が成立しなければ停止。
- 注文後は自動停止し、連続売買しない。

禁止事項:

- 連続注文。
- 自動再エントリー。
- APIエラー時の自動retry注文。
- ナンピン、マーチン、追撃、ポジション追加。
- 複数通貨、M5以上への同時拡張。
- schedule / cron / 常駐bot。

## 9. Phase 3D 極小実資金検証条件

Phase 3Dに進むための条件:

```text
Phase 2E-5短期3回確認完了
Phase 2F Public shadow risk/audit安定性レビュー完了
Phase 3A設計レビュー完了
Phase 3B Private API read-only実装・接続確認完了
Phase 3C Live Verification Mode設計レビュー完了
注文API実装前レビュー完了
APIキー / secret管理と失効手順確認済み
実注文前チェックリスト完了
ユーザーの明示承認あり
```

Phase 3D初回検証の上限案:

- 100通貨。
- 1注文だけ。
- 手動実行だけ。
- 実行前に残高、建玉、未約定注文、注文履歴をread-only確認。
- 実行後に即停止し、結果をレビューする。

Phase 3Dでも、収益性判断、自動売買開始、数量拡大、複数回実行は行わない。

## 10. 実注文前チェックリスト

実注文前に必要な確認案:

```text
git status clean
実行環境がlocalである
Render / Vercel / productionではない
backend/app/main_readonly.pyに変更なし
frontendに実注文導線なし
APIキーがterminal / docs / logs / git diffに表示されていない
.envがtracking対象ではない
raw response / headersを保存しない
残高照会成功
建玉照会成功
未約定注文照会成功
既存建玉なし
未約定注文なし
対象symbolはUSD_JPY
unitsは100
orders_countは1
manual confirmationあり
kill switch inactive
safety violation 0
risk decisionとorder intentの相関成立
auto_retry=false
auto_reentry=false
schedule / cron / botなし
```

## 11. 停止条件

次のいずれかが出た場合は、Phase 3B以降へ進まない。

- APIキー / secretが表示、保存、commit、ログ出力された。
- `.env`またはcredentialファイルがtracking対象になった。
- read-onlyでないAPI呼び出しが混入した。
- order、cancel、amend、broker送信関数がPhase 3B範囲へ混入した。
- 残高、建玉、注文履歴のread-only照会が失敗し、原因が説明できない。
- 既存建玉または未約定注文がある。
- candidate / risk decision / order intentの相関が崩れた。
- kill switchがactive。
- safety violationが1件でもある。
- summary、audit log、検証レポートが壊れた。
- raw responseやheadersが保存された。
- ユーザーの明示承認がない。

停止時は修正を急がず、docsレビュー、offline test設計、実装範囲の再確認へ戻る。

## 12. Phase 2E-5 / Phase 2Fとの関係

Phase 3A準備は、Phase 2E-5を飛ばすためのものではない。

ここまでに定義・実施した順序:

1. 別日にPhase 2E-5 2回目を1回だけ実行する。
2. 別日にPhase 2E-5 3回目を1回だけ実行する。
3. Phase 2FでPublic shadow risk/auditの安定性レビューと運用計画をまとめる。
4. Phase 3Aロードマップをレビューする。
5. Phase 3B-0でPrivate API read-only公式仕様確認・実装設計を行う。
6. 条件を満たす場合に限り、Phase 3B-1 mocked skeletonを別タスクで検討する。

Phase 2FはPrivate APIではない。Public shadow risk/auditのレビュー・安定性評価・運用計画である。

## 13. 実資金検証までの距離感

現時点では、実資金検証に進むにはまだ早い。

理由:

- Phase 2E-5短期確認、Phase 2F、Phase 2G、Phase 3B-0は完了したが、Private API read-only実装がない。
- APIキー / secret管理の実装確認がない。
- Live Verification Modeが未設計・未実装。
- 注文API実装前レビューが未完了。
- 100通貨・1回だけの実行前チェックリストが未運用。

したがって、本書作成時点で許可されるのは設計レビューまでである。

## 14. まだ進まない範囲

```text
Private API接続
APIキー入力・表示・保存
.env表示・変更
.env.example変更
broker実装
OrderRequest実装
OrderCandidateからOrderRequestへの変換
注文API
注文変更
注文取消
実注文
実資金
自動売買
Live Verification Mode実装
本番公開API追加
frontend変更
DB本番化
認証
cron / schedule / 常駐bot
Phase 3B / Phase 3C / Phase 3D実行
```

## 15. 結論

Phase 3A準備では、Private API read-onlyとLive Verification、極小実資金検証までの道筋を安全に分解した。

結論:

- Phase 2E-5短期確認、Phase 2F、Phase 2G、Phase 3B-0は完了済みである。
- Private APIはread-only設計から始め、注文機能とは分離する。
- APIキー / secretは実装前から表示・保存・commit禁止を徹底する。
- Phase 3B-1 mocked skeleton、Phase 3B-2 mocked endpoint tests、Phase 3B-3 preconnect review、
  Phase 3B-4 read-onlyローカル接続確認は完了済みである。
- 次に進む場合は、Phase 3C Live Verification Mode設計を別タスクで扱う。
- 極小実資金検証は、複数段階のレビューと明示承認を通過した後の将来フェーズである。
