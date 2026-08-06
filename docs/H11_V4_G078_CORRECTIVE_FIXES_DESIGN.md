> **[SUPERSEDED 2026-08-06]** この世代は削除済み。現行は G075（HANDOFF 参照）

# H-11 v4 G078 Corrective Fixes 設計書（no-POST・fake-only）

- 日付: 2026-08-05
- 対象: G077（`H11_AUTO_30M_20260805_G077`）に対する独立A/S/Oレビュー指摘の修正
- ステータス: **corrective generation（G078）・実装済み**
- 前提: G077はimmutable predecessorとして保持。G078は新reviewed-files digest /
  generation digestで再凍結。実Keychain・Private API・broker write・通知・ARM・
  LaunchAgent操作は一切行わない。

## 1. 修正対象（独立A/S/Oレビュー指摘）

| 指摘 | 内容 | 修正 |
|---|---|---|
| MEDIUM-1 | pre-start拒否（start-window超過等）でUNKNOWN write outcomeが未解決のままHALTなしに残る | **C1**: 開始窓超過・予算枯渇の拒否時にpersistent HALTをlatchしてからraise |
| LOW-1 | evidence→budget書込順のcrash窓でbudgetがundercountしうる | **C2**: budgetをper-scope evidenceファイル数から導出（別台帳を廃止） |
| LOW-2 | 破損budgetで`int()`がraw ValueError | **C2**: budget台帳自体を廃止（破損対象なし） |
| LOW-3 | start windowがwall clock依存（NTP skew感受性） | **C3**: `unknown_observed_monotonic`供給時はmonotonicでも15秒窓を強制 |
| INFO-1 | budget破損時status投影が`resolutions_used=-1` | **C2**: evidence数から導出（-1経路なし） |
| (追加) | budget checkがlock外でraceしうる | **C4**: budget checkをflock内で実施 |

## 2. 修正設計（G078 runtime）

### C1: pre-start拒否はterminal（HALT latch）

- `G078_RESOLUTION_START_WINDOW_EXCEEDED`（wall clock 15秒超過、または
  `unknown_observed_monotonic`供給時はmonotonic 15秒超過）:
  `engage_g078_halt(reason="G078_RESOLUTION_START_WINDOW_EXCEEDED")` をlatchしてからraise。
- `G078_RESOLUTION_BUDGET_EXCEEDED`（evidence数>=3）:
  `engage_g078_halt(reason="G078_RESOLUTION_BUDGET_EXHAUSTED_TERMINAL")` をlatchしてからraise。
- どちらも**markerは作成しない**（解決は開始されていない）。HALT fileがterminal記録の唯一の証跡。
- 他のpre-start拒否（digest不正・非fake port・scope既存・lock保持）はcaller bugとして
  raiseのみ（state不変）。runtime結線stepはUNKNOWN実在時にこれらもterminal扱いする。

### C2: budgetをevidence導出に変更

- `g078-resolution.budget.json`（台帳）を**廃止**。`_resolution_evidence_count()`が
  per-scope evidenceファイル数を数える。
- evidence fileは解決完了ごとの**単一の原子的書込** → crash時にもbudgetと実態が乖離しない。
- markerのみでevidence未書込の解決は「完了していない」＝budgetを消費しない。
- status投影の`resolutions_used`もevidence数から導出（-1経路なし）。

### C3: monotonic start window（LOW-3）

- `run_g078_unknown_resolution_once`に`unknown_observed_monotonic: float | None = None`を追加。
- 供給時: `monotonic() - unknown_observed_monotonic > 15秒` でも
  `G078_RESOLUTION_START_WINDOW_EXCEEDED`（C1どおりHALT latch）。
- 非供給時: wall clockのみ（従来どおり・文書化）。

### C4: budget checkをlock内へ

- flock取得後にevidence数を再確認してからmarker作成。並行プロセスがstale countで
  同時に通過するraceを排除。

## 3. 契約上の不変境界（G077から不変）

- write 1 attempt / action。retry・repost・second attempt 0。
- read-back: 3 endpoint各最大1回 / 解決step。GET間隔0.25秒以上（max 4/sec）。
- 開始窓15秒（wall + monotonic）・完了予算60秒（monotonic）。
- 解決予算: 最大3 / generation・各scope最大1回（evidence導出）。
- `actual_post_authorized=false` / `broker_post_authorized=false` / `entry_authorized=false`
  をevidenceに固定。`__bool__`は常にfalse。aggregate allow・permit・hard-guard解除値なし。
- UNRESOLVED / PARTIAL / TERMINAL policy はpersistent HALT。
- CONFIRMED_NOT_EXECUTEDは次scheduled cycle（新M1 slot）の新規観測としてのみ再評価。
- fake-only: `G078FakeOnlyCallable`以外のread-back portを拒否。
- moduleからhttpx/Keychain/smtplib/subprocess/requests/Pushover到達をsource scanで禁止。

## 4. 実装ファイル

| ファイル | 種別 |
|---|---|
| `docs/H11_V4_G078_CORRECTIVE_FIXES_DESIGN.md` | 本設計書 |
| `backend/app/services/h11_v4_g078_runtime.py` | 修正版解決step（G077のsuccessor） |
| `backend/app/tests/h11_auto/test_v4_g078_unknown_resolution_fake_only.py` | fake-onlyテスト（C1-C4対応） |
| `backend/h11_v4_g078_reviewed_digest.py` | G078専用reviewed-files digest / generation digest |
| `docs/templates/h11_v4_g078_frozen_generation.json` | G078凍結generation |

G077のruntime/test/digest/template/設計書は**一切変更しない**（immutable predecessor）。

## 5. acceptance matrix（G078追加分）

1. start-window超過（wall）→ raise + HALT（reason G078_RESOLUTION_START_WINDOW_EXCEEDED）
2. start-window超過（monotonic供給時）→ raise + HALT（同reason）
3. 予算枯渇（3解決後の4 scope目）→ raise + HALT（reason G078_RESOLUTION_BUDGET_EXHAUSTED_TERMINAL）
4. budget台帳ファイルが存在しない（evidence導出）
5. status投影の`resolutions_used`がevidence数と一致
6. budget checkがlock内で実施（lock保持中のbudget checkは拒否）
7. 既存G077 acceptance matrix（scope marker・pacing・timeout・partial・action kind別等）は
   G078でも全件PASS

## 6. Definition of done

- acceptance matrix全件PASS・focused/related tests・Ruff・diff check CLEAR
- G078 digestが実ファイルと束縛整合（binding field null化で自己無矛盾）
- 既存G077 tests無変更で全件PASS（G077はimmutable）
- フルスイート（backend/ CI構成）全緑
- 実Keychain・Private API・broker・通知・ARM・LaunchAgentへ未接続
- `actual_post_authorized=false` / `broker_post_authorized=false` / `live_ready=false` /
  `unattended_live_supported=false` を維持
