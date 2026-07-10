# H-11 v2 — TREND単独expert方向確率モデル Spec Freeze（no-POST）

Date: 2026-07-11
Hypothesis ID: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`（version 2）
Status: **FROZEN**（operator承認 2026-07-11・推奨(b)採択）
Supersedes: v1（config_hash=sha256:7bff1ee4… — development不支持・DISCONTINUED_DEVELOPMENT）

```text
frozen_spec=true
config_hash=（本docの導入コミットblobのSHA-256。freeze記録欄に記載）
formal_test=RESERVED_FORWARD_FROM_2026-07-11_NOT_COLLECTED（v1と同一予約・未接触）
current_stage=SPEC_FROZEN_PRE_STAGE1
actual_post=false / entry_post=false / settlement_post=false / post_count=0
performance_proof_status=false / live_ready=false / unattended_live_supported=false
```

## 1. Corrective rationale（事前記録）

v1のdevelopment validation（[記録](H11_DEVELOPMENT_TRAINING_NO_POST_20260711.md)）で:
(a) MoEのequal-weight比改善は相対+0.03%（支持基準1%の約1/30）、
(b) 単独TREND expert（Brier 0.240766）がMoE（0.241212）を上回った。
soft routerは開発区間で予測価値を追加していないため、**より低容量で説明可能な
単独TREND expert構造**へ変更する。これはv1の凍結値の場当たり変更ではなく、
ACTIVE policy §4に基づく**新version・新config_hashの別実験**である。
v1のformal test枠は消費していない（forward未接触）。

## 2. v1からの変更点（これ以外は全てv1凍結値を継承）

| 項目 | v1 | v2 |
|---|---|---|
| モデル構造 | 3 expert + softmax router | **TREND_CONTINUATION expert 単独**（L2ロジスティック・3特徴量・4パラメータ） |
| router | 線形softmax（18パラメータ） | **なし** |
| expert_weights出力 | 3値（和1） | (1.0,) 固定 |
| model_uncertainty | weight加重expert分散 | **0.0 固定**（単独モデルのため未定義。abstentionはno-trade band（0.42–0.58）のみ） |
| maximum_expert_disagreement | >0.40でHOLD | **非適用**（単独expert） |
| 主比較（採点時） | MoE vs equal-weight | **v2 vs p=0.5 baseline & vs 直接モデル（9特徴量単一ロジスティック）**。支持基準: baseline比 相対1%以上のBrier改善 + CI 0除外 + 両subperiod符号一致（v1 §3の統計則を継承） |
| regime軸 | router入力 | **out-of-domain gating専用に維持**（域外→BLOCKED。fail-closed適格性はv1と同一） |

予算・停止基準・執行境界（threshold 0.58/0.42・SL/TP・サイズ・時間帯・event除外・
model health・restart・Stage契約）は**v1凍結値をそのまま継承**する。

## 3. Freeze記録

- operator承認: 2026-07-11（v1 development結果の提示を受け、推奨(b)を明示採択）
- config_hash: `sha256:483fa9e4cc094251c3b3bfc5daaa007242a3385ba41c57caa95e5106fa4c4af3`
  （導入コミット `b4dbe5f` 時点の本doc全文のSHA-256。本欄の追記はhash対象外）
- 本結果を見た後の同一config_hashでの変更禁止はv2にも適用（変更=v3として再登録）

## 4. Development validation 記録（safe aggregate・formal test ではない）

同一development区間（v1と同一cache・同一分割・4,624予測・coverage 1.0）:

| 指標 | 値 |
|---|---|
| Brier v2（TREND単独） | 0.240766 |
| Brier 直接モデル（9特徴量） | 0.239992 |
| Brier baseline (p=0.5) | 0.25 |
| baseline比 相対改善 | **+3.69%**（支持基準1%を上回る） |
| Log loss v2 / 直接モデル | 0.674583 / 0.673011 |

誠実な注記:
- baseline比では凍結支持基準（相対1%）を development 段階で満たす。ただし CI・subperiod
  符号一致の統計則は **formal test（forward・未収集）でのみ判定**する。本結果は edge 証拠ではない。
- 直接モデル（9特徴量）が v2 をわずかに上回る（相対 +0.32%）が、1% 未満であり
  低容量・説明可能性を優先する v2 の構造選択を覆さない（v1 の「複雑化には 1% 以上の
  正当化を要する」原則の対称適用）。
- 学習済みパラメータ: `backend/app/strategies/h11_parameters_v2.json`（config_hash 刻印済み）。
