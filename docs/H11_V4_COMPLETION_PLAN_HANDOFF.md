# H-11 v4 完成計画 — 外部実装者向け引き継ぎ文書

> **[状態: 履歴文書 — 2026-08-07 時点]**
> 作成は 2026-08-05、基準コミットは `5df62a3` である。**この文書に書かれた
> HEAD・digest・行番号・テスト件数はすべてその時点の値であり、現在の実測値とは
> 一致しない。** 以後 Phase A/C/D/E/F/G が完了し、コードも digest も繰り返し
> 動いている。値が必要なときは必ず §0.2 のコマンドで再計算すること。
>
> **現在の運用手順の権威は `docs/H11_V4_OPERATOR_COMMISSIONING_RUNBOOK.md`**
> である。本文書は計画の経緯・設計判断・禁止事項の記録として残す。

`docs/` 配下の他の設計文書(特に G066〜G079関連)は削除済み世代を前提としており、
参照してはならない。

---

## 0. この文書の読み方

- **設計・仕様・受け入れテストは orchestrator(Claude)が作成する。**
- **実装は外部が行う。** 外部実装者は自分の受け入れテストを書かない(§1 規則2)。
- 各作業項目には「完了条件」が明記されている。曖昧な場合は実装せず質問すること。

### 0.1 作業前に必ず実行する環境確認

```bash
cd /Users/naoikansui/Desktop/トレード
git rev-parse HEAD          # 作成時点は 5df62a3。現在は前進しているのが正常
git status --short          # 期待: 空(dirty なら着手しない)
cd backend && .venv/bin/python -m pytest app/tests/ -q | tail -3
                            # 期待: 0 failed（件数は増加が正常なので固定値で判定しないこと。
                            #        Keychain 権限の無い環境では keychain テスト2件が error になる）
```

**HEAD は既に `5df62a3` より前進しており、この文書の行番号・digest 値は信用できない。**
上記のとおり値は必ず再計算すること。
本リポジトリでは過去に、作業中に別プロセスが14世代を並行コミットし、
修正対象が消滅した事故が起きている。着手前の確認は必須。

### 0.2 この文書で使う digest 値の再計算方法

文書中の digest は 2026-08-05 / `5df62a3` 時点の実測値である。自分で再計算する場合:

```bash
cd backend
# reviewed-files digest
.venv/bin/python -c "from pathlib import Path; from h11_v4_reviewed_digest import compute_reviewed_files_digest; print(compute_reviewed_files_digest(repository=Path('..').resolve()))"
# generation digest
.venv/bin/python -c "
from pathlib import Path
from h11_v4_reviewed_digest import compute_reviewed_files_digest
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
repo=Path('..').resolve()
print(load_v4_gmo_frozen_generation(repository=repo, implementation_digest=compute_reviewed_files_digest(repository=repo)).digest)
"
```

`5df62a3` 時点の値(**歴史的参照のみ。現在値ではない**):

| 値 | 期待 |
|---|---|
| reviewed-files digest | `sha256:e4ef87a0c5c4da5847f9e45b854ceb23dd62d01675d4e01136667a7b2c3aac62` |
| generation digest | `sha256:ffb405bc92fef1bf1279e4758077ffe9f11e904dae2f6a46e48465b97bcfbd66` |
| canonical 世代ラベル | `H11_AUTO_30M_20260802_G075` |

---

### レビュー依頼時の注意（2026-08-07 追記）

独立レビューを外部環境に依頼する場合、**フルスイートの合格件数を固定値で要求しない**こと。
macOS Keychain への書き込み権限が無い実行環境では
`backend/app/tests/test_h11_v3_keychain_credential_no_post.py` の2件が必ず error になり、
コードとは無関係の VETO を生む（2026-08-07 に Architecture / Operations の2レーンで発生）。
「当該2件を除いて 0 failed であること」と指定すること。

同様に、HEAD・digest・テスト件数の具体値を手順書に書かないこと。値はコード変更のたびに
動き、この文書と運用 runbook は過去3回、値の陳腐化で指摘を受けている。§0 の再計算
コマンドに置き換え、「いつ時点の実測か」だけを添えること。

## 1. 不変の運用規則(例外なし)

2026-07-22〜08-05 の約2週間で G013→G079 まで世代が量産され、**エントリーに成功した
世代は1つも無かった**。原因は能力不足ではなく、以下5点の欠落だった。**すべての作業に
例外なく適用する。**

1. **世代を増やさない。** 修正は canonical 世代(G075)内で digest 再ベイクのみ。
   G076以降を新規作成しない。「clone-edit して次の世代」は禁止。
2. **受け入れテストは実装者が書かない。** orchestrator が先に書き、実装者はそれを
   通す。実装者がテストを書くと、実装を鏡写しにするだけで欠陥を検出できない
   (実績: 46件全パスの裏で P0 が3件通過した)。
3. **レビュー合格証を、ゲートを通すために書き換えない。**
   `h11_v4_g075_independent_review_attestation.json` /
   `..._runtime_commissioning_evidence.json` の digest を「ゲートが通らないから」
   という理由で更新することは**禁止**。これは未レビューのコードに過去の CLEAR 判定を
   移植する行為であり、本プロジェクトが過去に VETO した自己署名パターンそのもの。
   digest 更新は「**本物のレビューを実施し、その結果を記録した副産物**」としてのみ
   発生してよい。
4. **能力フラグを動かす前に独立3レーンレビュー。**
   `live_ready` / `unattended_live_supported` / `actual_post_authorized` のいずれかを
   true にする変更は、Architecture / Safety / Operations の3独立レビューを経ること。
5. **「無人」を宣言する前に必ず実機soak。** 本システムで実際に起きた障害
   (Ctrl-C永久HALT、常駐が15秒で自殺、iCloudによる`.git`破損、plist digest陳腐化)は
   **単体テストで1件も検出できていない**。弱点はコード論理ではなく時間と環境にある。

---

## 2. 完成の段階的定義

目標が「UI ONで自動売買」「無人稼働」「1コマンド実行」の間で揺れると見積もりが
不可能になるため、各段階の完成条件を固定する。

| 段階 | 完成条件 |
|---|---|
| **P0** | すべてのゲートの拒否理由が真実で、全参照が解決する |
| **P1** | 3つの構造欠陥(偽UNKNOWN / 状態同一性 / 静かな死)が塞がれた |
| **P2** | **1コマンドで1回**、エントリー→保護→決済→フラット確認まで完走。途中でプロセスが死んでも次のtickで再開する |
| **P3** | 上記が**人の操作なしで**、48時間の実機soakを越える |
| **P4** | UI/ARM の是非を判断(**意図的に最後**) |

**P2 で「エントリー判断・執行・保護・決済が全自動」に到達する。** 無人ではないが、
機械としては動く状態。

---

## 3. P0: VETO状態の解消(新機能ゼロ)

3本の独立レビューが出した VETO は、**新機能を一切足さずに**解消できる。

### P0-a: manifest に半分残った改ざんの撤去 【最優先】

**背景**: digest 再ベイク時に、レビュー合格証を現行コードに貼り替える試みが行われ、
artifact 2ファイルは revert されたが、**manifest 側の束縛 digest が改ざん版のまま
コミットされている**。

対象: `docs/templates/h11_v4_g075_frozen_generation.json` および
`docs/templates/h11_v4_gmo_frozen_generation.json`(両者は byte 一致を保つこと)

| フィールド | 現在(改ざん版) | 正しい値(実 artifact のハッシュ) |
|---|---|---|
| `runtime_commissioning_evidence_digest` | `sha256:801ef9fd…` | `sha256:78a59684a61a08e2b874ac9665aab25aeb94fe46335ba5392ee865084e7adff0` |
| `successor_halt_release_digest` | `sha256:2a6c9969…` | `sha256:0591aadb401c5ad1835332fa6f46b9bb9711f48312cb997a0892cf7cde906667` |

**この作業は固定点反復を必要としない**(実測で確認済み)。理由:

1. **reviewed-files digest は動かない。** `h11_v4_g075_frozen_generation.json` は
   `_G070_NORMALIZED_ARTIFACTS` に含まれ、変更する2フィールドはどちらも
   `_G070_BINDING_FIELDS`(`backend/h11_v4_reviewed_digest.py:237-253`)で
   null 化されてからハッシュされる。
2. **`generation.digest` も動かない。** `V4GmoFrozenGeneration.digest` は
   canonical_json からこの2フィールドを除外する
   (`backend/app/h11_auto/v4_gmo_generation.py`)。
   実測: 修正前後とも `sha256:ffb405bc92fef1bf1279e4758077ffe9f11e904dae2f6a46e48465b97bcfbd66`。
3. `docs/templates/h11_v4_gmo_frozen_generation.json`(canonical)は
   そもそも `REVIEWED_FILES` に**含まれない**。

したがって **2ファイルの2フィールドを書き換えて終わり**。他の digest の再計算は不要。

**完了条件**:
- 両 manifest の当該2フィールドが、対応する artifact の `artifact_digest` と一致する
  (= 実 artifact のハッシュ)
- 2つの manifest が byte 一致を保つ
- reviewed-files digest と generation digest が §0.2 の期待値から**動いていない**
- ゲート `verify_g075_review_artifacts` は**引き続き拒否する**
  (=未レビュー状態を正しく表明)。**ゲートを通そうとしないこと**(§1 規則3)

**検証コマンド**:
```bash
cd backend && .venv/bin/python -c "
import json
from pathlib import Path
from app.services.h11_v4_g075_runtime import _canonical_hash
T=Path('../docs/templates')
m=json.loads((T/'h11_v4_g075_frozen_generation.json').read_text())
c=json.loads((T/'h11_v4_gmo_frozen_generation.json').read_text())
assert m==c, 'canonical と template が不一致'
for name,field in (('runtime_commissioning_evidence','runtime_commissioning_evidence_digest'),
                   ('independent_review_attestation','successor_halt_release_digest')):
    a=json.loads((T/f'h11_v4_g075_{name}.json').read_text())
    real=_canonical_hash({k:v for k,v in a.items() if k!='artifact_digest'})
    assert a['artifact_digest']==real, f'{name}: artifact 自身が壊れている'
    assert m[field]==real, f'{field}: manifest が実 artifact を指していない'
print('P0-a OK')
"
```

### P0-b: 孤児化した永久HALTの明示的継承 【構造上の最重要】

**背景**: state root は `generation.digest` で決まり(`v4_gmo_runtime_paths.py:27-31`)、
それは `implementation_digest` を含む。digest 再ベイクにより state root が
`generation-f0e74bf0…` → `generation-ffb405bc…`(未作成)へ移動し、旧 root に
latch されていた永久HALT が孤児化した。

```
backend/market_data/h11_v4_gmo_actual_runtime/generation-f0e74bf0…/g075-persistent-halt.json
  → {"reason": "G075_INITIAL_TRANSACTION_UNKNOWN", "status": "HALTED",
     "broker_post_count": 0, "actual_post_count": 0}
```

**これは2度目である。** G074 にも同一パターンの
`G074_INITIAL_TRANSACTION_UNKNOWN` が latch されており、その digest
(`sha256:ce098ee8…`)は canonical manifest の
`activation_source_generation_digest` そのもの。つまり
**「latch された未解決HALTから、新しい digest を発行して脱出する」**のが
世代量産の実態の一部だった可能性が高い。

さらに `5df62a3` は、その履歴を記録していた3フィールドを削除している:
`predecessor_generation_digest` / `predecessor_initial_activation_unknown` /
`predecessor_terminal_evidence_reused`。

**作業**:

**(1) canonical manifest と G075 template の両方に、以下2フィールドを復元する。**

| フィールド | 値 |
|---|---|
| `predecessor_generation_digest` | `sha256:f0e74bf0f3ef114db3474df4aa7348edf112a5c8534d55121f730173ea868c0d` |
| `predecessor_initial_activation_unknown` | `true` |

`f0e74bf0…` は **G075 自身の再ベイク前の generation digest** であり、
孤児化した HALT が存在する state root
(`backend/market_data/h11_v4_gmo_actual_runtime/generation-f0e74bf0…/`)に対応する。

**警告**: この2フィールドは `_G070_BINDING_FIELDS` に**含まれない**ため、
追加すると reviewed-files digest と generation digest が**両方動く**
(P0-a とは異なる)。したがって:
- P0-a を先に完了させてから P0-b に着手すること
- 追加後、reviewed-files digest を再計算し、両 manifest の
  `implementation_digest` に焼き直す
- **固定点に収束するまで反復する**(G075 template は `REVIEWED_FILES` 内だが
  `implementation_digest` は null 化されるため、通常1〜2回で収束する)
- 収束後、`docs/templates/h11_v4_g075_runtime_commissioning_evidence.json` と
  `..._independent_review_attestation.json` は**触らない**(§1 規則3)。
  ゲートは引き続き拒否したままでよい

**(2) G075 の HALT 検査が predecessor の state root も参照するようにする。**

現状、G075 の HALT 検査は current state root しか見ない:
`backend/app/services/h11_v4_g075_runtime.py:1013, 1066-1067, 1343-1346`。

流用元(既存実装): `backend/app/h11_auto/v4_gmo_monitor_supervisor.py:650, 695` の
`release.predecessor_halt_generation_digest` — G064/G065 系には
predecessor 継承の仕組みが既にある。

**設計要件**:
- `predecessor_generation_digest` が非 null のとき、その state root の
  `g075-persistent-halt.json`(および G074 形式 `g074-persistent-halt.json`)を検査する
- 未解決の HALT が存在すれば、current state root が綺麗でも**起動を拒否する**
- 拒否理由は既存の安全ラベル形式に従う
  (例: `G075_PREDECESSOR_HALT_UNRESOLVED`)
- **HALT を解除する経路をこの作業で追加しないこと。** 解除は operator の明示操作を
  要する別設計であり、P0 の範囲外

**完了条件**:
- canonical G075 を起動しようとすると、predecessor の未解決 HALT を理由に拒否される
- **digest を変えるだけでは HALT から脱出できない**ことがテストで固定される
  (受け入れテストは orchestrator が提供)
- reviewed-files digest / generation digest が固定点に収束し、
  両 manifest が byte 一致を保つ

**注**: 両 HALT とも `broker_post_count: 0` / `actual_post_count: 0` であり、
実発注は発生していない。**現時点で実資金への影響はゼロ。** 塞ぐべきは仕組み。
なお、これらの HALT は §4 R1 の偽 UNKNOWN(注文を試みていないのに「結果不明」と
記録される)によって生成された可能性が高い。R1 を修正すれば同種の HALT は
今後発生しなくなるが、**既存の latch を消してよいことにはならない**。

### P0-c: Monday self-check の参照切れ修正

`backend/scripts/h11_auto_v4_monday_self_check.py` が、`5df62a3` で削除された
テストファイルを参照している:

| 行 | 参照先 | 用途 |
|---|---|---|
| 30 | `app/tests/h11_auto/test_v4_monday_self_check_no_post.py` | `FOCUSED_TESTS` |
| 40 | `app/tests/h11_auto/test_v4_g063_generation_manifest_no_post.py` | `FOCUSED_TESTS` |
| 77 | `app/tests/h11_auto/test_v4_monday_self_check_no_post.py` | `RUFF_TARGETS` |

いずれも存在しないため、このスクリプトは恒久的に失敗する。
また `:16, :199` が `G064_GENERATION_LABEL` をハードコードしており、canonical G075 に
未対応。

**完了条件**: 削除済み参照を除去し、canonical 世代(G075)を認識する。
世代ラベルは canonical 定数(`h11_v4_g075_runtime.py:25` の `G075_GENERATION_LABEL`)
から import し、**リテラルを新たに増やさない**。

**注**: このスクリプトは現在どの定期手順にも組み込まれていない(参照は
`docs/H11_V4_OPERATOR_COMMISSIONING_RUNBOOK.md` と `REVIEWED_FILES` のみ、
crontab/LaunchAgent 登録なし)。**P0 では動くように直すだけでよい。**
定期実行への組み込みは P3 で判断する。

### P0-d: 準備ゲートに canonical 世代を登録

`_PREPARATION_KNOWN_GENERATION_LABELS`
(`backend/app/h11_auto/v4_actual_preparation_guard.py:1448`)に
`H11_AUTO_30M_20260802_G075` が**存在しない**(実測確認済み)。
`load_external_preparation_gate`(`:2167`)が
`PREPARATION_FROZEN_GENERATION_MISMATCH` で拒否するため、
**11の日次準備操作すべてと G013 canary 経路が死んでいる**。

該当箇所の構造:
```python
_PREPARATION_KNOWN_GENERATION_LABELS = _RUNTIME_ONLY_TARGET_GENERATION_LABELS | {
    "H11_AUTO_30M_20260728_G019",
    ...
    "H11_AUTO_30M_20260801_G065",
}
```
G075 はどちらの集合にも不在。

**設計判断(実装者が迷わないよう明示)**: G075 は runtime-only 世代なので、
`_RUNTIME_ONLY_TARGET_GENERATION_LABELS` 側に追加するのが意味的に正しい。
ただし**リテラルを直書きせず**、`G075_GENERATION_LABEL` を import して使うこと
(§1 規則1 の精神。同種のラベルドリフトが過去に2回 VETO を招いている)。
循環 import が発生する場合は orchestrator に報告すること
(定数の置き場所を変える設計判断が必要になる)。

**完了条件**: 日次準備バンドル
(`backend/scripts/h11_auto_v4_daily_preparation_bundle.py --stage 1`)が
`PREPARATION_FROZEN_GENERATION_MISMATCH` 以外の理由で進行する。

**重要**: 他のゲート(git clean、digest、P0-b の predecessor HALT など)で
止まるのは**正常であり、修正対象ではない**。P0-d のゴールは
「準備ゲートが canonical 世代を認識する」ことだけ。
**このコマンドを最後まで通そうとしないこと**(実 Pushover/SMTP 送信や
Private API 呼び出しを伴うため、実行は operator の判断に属する)。

### P0-e: ARM制御APIのテスト復元

`backend/app/tests/h11_manual/test_unattended_control_api_no_post.py`(315行・10テスト)が
`5df62a3` で削除され、未復元。これは**生存モジュール**
`app/h11_manual/unattended_control_api.py`(同コミットで −410行 改変)の唯一の
振る舞いテストだった。

特に `unattended_auto_mode_requested()`
(`unattended_control_api.py:164-179`、消費側 `app/h11_manual/api.py:67`)は
**ARM中/HALT中に手動 Private GET を遮断する連動装置**であり、現在テストゼロ。

**この項目は orchestrator が担当する**(§1 規則2 との整合)。テストの復元は
テスト作成そのものであり、実装者に委ねると「実装を鏡写しにしたテスト」に
なるため。外部実装者はこの項目を実施しない。

**完了条件**(orchestrator 側): `unattended_auto_mode_requested()` を含む
control API の振る舞いテストが復活し、削除済み世代への依存が無い形で通る。

### P0-f: 運用文書の更新

- `docs/H11_V4_OPERATOR_COMMISSIONING_RUNBOOK.md`: 冒頭が「G076/G077/G078状態」、
  `:12` が G076 を canonical と明記、`:50` の期待出力も G076。**全面的に誤り。**
- `AGENTS.md`: G077/G078/G079 の例外セクションが削除済みモジュールを参照。

**Phase A で解消済み**: 両ファイルとも G075 基準へ更新済み(AGENTS.md の G076-G079 参照は
49箇所→0、RUNBOOK は G075 基準へ全面書き換え)。AGENTS.md は `REVIEWED_FILES` 内のため、
編集時は digest 再ベイクが必要(実施済み)。

---

## 4. P1: 3つの構造欠陥(機能追加の前提)

### R1: 偽UNKNOWN の根絶 【churn の震源】

`backend/app/services/h11_v4_g075_runtime.py:782` の `except BaseException` が、
**内部エラーを含むあらゆる例外**を `status: UNKNOWN`(=「外部で注文が発火した
かもしれない」)と記録し、永久HALTを latch する。

実際に起きていること: bootstrap が `entry_runner` を渡さないため
(`h11_auto_v4_g075_runtime_bootstrap.py:107`)、`_run_entry_actual`
(`h11_v4_g075_live_runtime.py:443-448`)が
`G075_GENERATION_TERMINAL_NO_ENTRY` を必ず投げる。それが上記で UNKNOWN に変換され、
**注文を1回も試みていないのに**「結果不明」として永久停止する。

**設計方針**: 「**送信前に失敗した**」と「**送信したが結果不明**」を型で区別する。
- 送信前失敗 → 再試行可能、HALT しない
- 送信後不明 → terminal(現行の扱いを維持)

この区別が無い限り、内部バグが毎回「実弾かもしれない事故」に化け、世代を作り直す
以外に復旧手段が無くなる。**これが世代量産の根本原因である。**

### R2: 状態同一性とコード digest の分離

state root が `generation.digest`(= コード digest を含む)で決まるため、
コードを直すたびに HALT・一回性マーカー・リスク台帳が孤児化する(P0-b 参照)。

**設計方針**: state root を `generation_label` + 明示的な `state_epoch` で決める。
epoch の前進は operator の明示操作のみ。コード修正では state が動かない。

### R3: 静かな死をなくす

- HALT時の通知が存在しない(`notification_attempt_count` は 0 固定)
- `KeepAlive=false` かつ `StartInterval` 無しで再起動しない
  (`v4_gmo_unattended_scheduler_launchd.py:112-116, 131, 136`)
- G075 を見る監視役が無い(`v4_gmo_monitor_supervisor.py` に G075 の分岐ゼロ)

**設計方針**: HALT時に Pushover/メールを送る(実 transport は検証済みのものを流用)。
tick 方式への移行(P2)で再起動問題も同時に解消する。

---

## 5. P2: 1コマンド = 1回の完全サイクル

**土台**: `backend/scripts/h11_auto_v4_g013_actual_canary.py`

これは **2026-07-27 に実際に約定した唯一の実績**を持つ経路である
(BUY 1000通貨 USD/JPY @163.542、OCO保護 SL 163.334 / TP 163.853、
`FILLED_PROTECTED` まで到達)。

**壊れているのは決済側1点のみ、原因も特定済み**:

```
backend/app/services/h11_v4_gmo_actual_runtime_driver.py
  :111  while True:            ← 常駐ループ
  :139  except BaseException:  ← あらゆる終了で永久HALT
```

呼び出し元: `h11_v4_gmo_g013_canary.py:797`
(`build_foreground_lifecycle_driver().run_until_flat()`)

このドライバはコメント通り「**LaunchAgentとしては絶対にインストールされず、
再起動機構も持たない**」設計で、Ctrl-C・スリープ・ログアウトで死亡し、
永久HALTを残す。2026-07-28 に実際に発生し、実建玉がブローカー側OCOのみで
放置された。

**作業**: `run_until_flat()` の常駐ループを tick 方式に作り替える。
- エントリー側スケジューラ(非常駐 `StartInterval`)が既に実績のある形
- `dispatch_once()` は既に1回実行型なので流用可能
- `except BaseException → 永久HALT` を廃し、R1 の型区別を適用する
  (プロセス終了は「次のtickで再開」、取引整合性の異常のみ HALT)

**完了条件**: operator が1コマンド実行 → エントリー→保護→決済→フラット確認まで
完走する。途中で**意図的にプロセスを kill しても、次の tick で再開**し、
永久HALT にならない。

---

## 6. P3: 無人化

P2 が**実際に1周完走した後**に着手する。tick 化が済んでいれば追加作業は小さい。

**48時間の実機soak**(最低24時間)を経てから「無人」を宣言する。soak で確認するもの:
スリープ→復帰、JST日付の切り替わり、launchd の実挙動、ハートビート連鎖の長時間挙動、
iCloud 同期による state 破損の有無。

---

## 7. P4: UI/ARM の判断

意図的に最後に置く。UI は今回「壊れた系を `READY` と表示する」という最も危険な嘘を
ついていた(`safe_g075_api_status` が `control_plane_state: READY`,
`persistent_halt: false` を返す一方、実機の LaunchAgent は digest 陳腐化で
起動失敗していた)。CLI 優先で進め、UI の是非は P3 到達後に判断する。

---

## 8. 役割分担と境界

**orchestrator(Claude)が行う**: 仕様書作成、受け入れテスト作成、外部実装の
敵対的レビュー、独立3レーンレビューの運営、digest 整合性の検証

**orchestrator が行わない**(operator 自身の操作):
実 credential の構築、ARM ON、LaunchAgent の実 install、有効化を宣言する push、実発注

---

## 9. 正直な但し書き — 経済性

**機械は完成させられる。ただし完成した機械が利益を出す根拠は、現時点で存在しない。**

2026-07-28 の実測(19ヶ月・実測 BID/ASK スプレッド):

| 項目 | 実測値 |
|---|---|
| SHORT_V1 の方向エッジ(30分) | +0.28〜0.32 pips/回 |
| 実測スプレッド | 約 0.40 pips |
| **差し引き** | **約 −0.1 pips/回** |

出口ルール(210通り総当たり)・入口閾値・時間帯・保有時間の**4方向すべて**で、
損益分岐を超える設定は**1つも見つからなかった**。勝ちの平均幅が負けの平均幅の
87〜96% しかない非対称性が主因。

**推奨**: **P2 到達(機械が動くことの証明)の時点で、経済性の判断を改めて行う。**
P3 以降に投資する前に決める方が合理的である。

---

## 10. 外部実装者が絶対にやってはいけないこと

以下はすべて、本リポジトリで**実際に発生した事故**に基づく。

| 禁止 | 理由(実績) |
|---|---|
| 新しい世代(G076以降)を作る | 14世代を量産し、エントリー成功はゼロだった |
| レビュー合格証の digest を、ゲートを通すために書き換える | 未レビューコードへの CLEAR 移植。過去に VETO 済み |
| ゲートが失敗するので**ゲート側**を緩める | 失敗しているのは常にデータか配線。ゲートは正しい |
| 自分でテストを書いて自分の実装を検証する | 46件全パスの裏で P0 が3件通過した |
| `except BaseException` を新規に追加する | 内部エラーが「実弾事故」に化ける(§4 R1) |
| 実 credential 構築 / 実 broker 通信 / 通知送信 | すべて operator の領域(§8) |
| LaunchAgent の install / bootout / bootstrap / kickstart | 同上 |
| ARM ON / OFF | 同上 |
| `market_data/` 配下の HALT・marker・ledger の削除や改変 | 未解決事象の証跡。消してはならない |
| 能力フラグ(`live_ready` / `unattended_live_supported` / `actual_post_authorized`)を true にする | 独立3レーンレビュー必須(§1 規則4) |
| 取引パラメータの変更 | USD_JPY / 30m / SHORT_V1 / 1000通貨 / 1800秒 / 30回・日 / 5000・10000・50000円 / 連敗5 は不変 |

**判断に迷ったら実装せず orchestrator に質問すること。** 本プロジェクトでは
「良かれと思って直した」結果が新しい P0 になった事例が繰り返されている。

---

## 11. 着手順序と各段階の手続き

```
【P0】 a → b → c/d/e/f(並行可)
         ↓
       orchestrator が受け入れテストを提供 → 実装 → 敵対的レビュー
         ↓
       独立3レーンレビュー(A/S/O)→ VETO なし → commit
         ↓
【P1】 R1 → R2 → R3(同じ手続き)
         ↓
【P2】 1コマンド完全サイクル → 実機で1周完走
         ↓
       ★★ 経済性の判断(§9)★★
         ↓
【P3】 48h soak → 【P4】 UI/ARM 判断
```

### 各作業の標準手続き

1. orchestrator が仕様と**受け入れテストを先に**提供する
2. 実装者はテストを受け取ってから着手する(テストは編集禁止)
3. 実装後、以下をすべて実行し結果を報告する:
   ```bash
   cd backend
   .venv/bin/python -m pytest app/tests/ -q | tail -3   # 全件パス必須
   .venv/bin/python -m ruff check app/ scripts/          # clean 必須
   cd .. && git diff --check                             # clean 必須
   ```
4. orchestrator が敵対的レビューを行う
5. 能力に関わる変更は独立3レーンレビューを経る
6. VETO が無ければ commit

### 報告に必ず含めること

- 変更したファイルと、その理由
- 全テスト結果(件数を明記。「通った」だけでは不可)
- **指示範囲外に触れた箇所があれば、その全て**
  (過去に指示外の4ファイルが変更され、レビューで初めて発覚した)
- 解決できなかった点は、取り繕わず明示する

---

## 12. 参考: この計画の前提となった検証結果

すべて 2026-08-05 までに実測で確認済み。推測は含まない。

| 事実 | 根拠 |
|---|---|
| G066〜G079 でエントリー成功した世代はゼロ | 実機の state root / launchctl / stderr ログ |
| G075 の実発注経路は存在し到達可能（エントリー成功はゼロ） | `h11_auto_v4_unattended_live_bounded_run.py:164` の SWITCH_ONLY 分岐は G064/G065 のみ。G075 は bounded runner CLI → orchestration → driver の経路で到達可能 |
| `G075_GENERATION_TERMINAL_NO_ENTRY`（`h11_v4_g075_live_runtime.py:448`）は意図的な封印 | 常駐 supervisor レーンが実credential/実transportを構築しないための単一呼び出し口契約の強制であり、欠落ではない |
| 偽 UNKNOWN → 永久HALT の連鎖 | `h11_v4_g075_runtime.py:782` + 実行再現 |
| G074/G075 に未解決 HALT が latch | `market_data/.../g07{4,5}-persistent-halt.json` |
| 実機 LaunchAgent は digest 陳腐化で停止中 | `launchctl print`(last exit code = 1) |
| 対話式 canary は実際に約定した | 2026-07-27、coordinator DB + 実市場 ASK と価格一致 |
| Ctrl-C で永久HALT・建玉が監視不在に | 2026-07-28 に実発生 |
| エッジ ≒ コスト(約 −0.1 pips/回) | 19ヶ月 M1 BID/ASK、出口210通り総当たり |

---

## 13. Phase C 完了の追記（2026-08-06）

Phase C（工学完成バッチ C-1〜C-5）はコミット後に独立3レーンレビューを経る。実装内容:

### C-1: R1 解消 — halt を焼く権限は真の送信境界のみ

- `h11_v4_gmo_actual_transport.py`（S0）: 送信 try の `except Exception` を
  `except BaseException` へ変更。Ctrl-C を含む送信中失敗でも POST は
  unknown-post callback（store latch）を経てから re-raise される。
- `h11_v4_gmo_coordinated_actual_path.py`（S1/S2/S3）と
  `h11_v4_gmo_actual_runtime_driver.py`（S4）: `except BaseException` 内の
  `engage_unknown_halt()` を削除。store が latch 済みなら re-raise、
  未 latch なら `V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT`（retryable）で
  分類し、偽 UNKNOWN 永久HALT を製造しない。
- G075 action wrapper（`h11_v4_g075_runtime.py`）: pre-dispatch 失敗は
  `.started.` を削除して `G075_ACTION_PRE_DISPATCH_FAILED_RETRYABLE`、
  分類不能は従来どおり UNKNOWN + halt（fail-safe 維持）。
  G075 live port も同じ分類を適用（ledger 欠損=未送信、ledger 読めず=
  分類不能）。
- 既存の意図的 latch（`_require_transport_boundary_dead_man`・再起動 pending
  回収）と `g013_canary.py:498` の `release_unattempted_reservation` は不変。

### C-2: HALT discharge（操作者手続き・rename アーカイブのみ）

- `app/services/h11_v4_halt_discharge.py` + `scripts/h11_auto_v4_halt_discharge.py`。
  削除禁止・`os.replace` による `g0*-halt-discharged.<UTC>.json` への
  rename アーカイブのみ。元内容は `original`、操作者記録は `resolution`
  （operator / reason / broker_state_confirmation / halt_content_sha256、
  実内容と一致必須）。1回1件・glob 一括解除なし・runtime からは不可達
  （AST テストで固定）。実 HALT 2件への適用は operator の明示操作。

### C-3: 表示系の正直化

- `safe_g075_api_status` が `halt_scan`（CLEAR / UNRESOLVED_HALT_PRESENT /
  SCAN_FAILED / NOT_CHECKED）と `persistent_halt`・`control_plane_state`
  を投影。スキャン失敗でも表示は絶対に例外を出さない。

### C-4: repository 引数の必須化

- `_capability_valid` / `G075ResidentSupervisor` / `safe_g075_api_status` /
  `load_g075_release_capability_digest` の `repository` を必須化（Phase A の
  opt-in を廃止）。`build_g075_recovery_scope`・G075 live runtime・bootstrap・
  control API を含む全呼び出し元を更新。
- `verify_g075_scheduler_binding` の `getattr` を明示属性アクセスへ変更。
