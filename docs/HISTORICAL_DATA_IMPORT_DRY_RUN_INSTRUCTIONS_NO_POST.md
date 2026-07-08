# Historical Data Import Dry-Run Instructions（no-POST・operator向け）

Step: `HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST` Phase 7
対象next Step: `HISTORICAL_DATA_IMPORT_DRY_RUN_WITH_OPERATOR_CSV_NO_POST`

## 1. operatorが次Stepで渡すもの

- `bid_csv_path` と `ask_csv_path`(推奨route: GMO Public klines BID+ASK)
  または `combined_csv_path`(spread列付きCSVがある場合)
- symbol(推奨: USD_JPY)/ timeframe(推奨: M5)
- date range(取得済み期間の宣言。train/validation/OOSを賄う長さ)
- source label(例: GMO_PUBLIC_KLINES_EXPORT_YYYYMMDD)
- timezone方針の確認(CSVのtimestampがUTC epochまたはTZ明示ISOであること)

## 2. file準備ガイダンス

- 置き場所はローカルの任意パスでよい(repo外推奨・repoにcommitしない)
- CSVはUTF-8・ヘッダ行必須。必須列は
  [HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md](HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md)
- **禁止列**(account/order/position/trade ID・credential・raw response系)を
  含めない(含まれていれば読取前にblockされる)
- 取得(public kline exportの実行)はoperator承認のもとで行う。
  Codexは承認なしに `fetch_gmo_public_market_data.py` を実行しない
- download・real HTTP・credentialは dry-run でも使わない(local fileのみ)

## 3. dry-runで実施するvalidation

adapter(`import_historical_csv`)が以下をfail-closedで検証する:

path妥当性(remote/directory/非csv block)→ header(必須列・禁止列)→
timestamp(UTC epoch/TZ明示・単調・重複なし)→ symbol/timeframe/source_label →
OHLC(数値・high>=low)→ spread(列またはbid/ask pair導出・負値block)→
session導出(JST policy)→ dataset構築 + `validate_backtest_dataset`。

## 4. safe result categories

- `CSV_INTAKE_READY_OFFICIAL_EVALUATION` — spread込みでofficial評価に進める
- `CSV_INTAKE_READY_REFERENCE_ONLY` — OHLCのみ。official不可(挙動確認用)
- `CSV_INTAKE_BLOCKED_*` — 各blocked理由(spread欠損 / TZ欠損 / 列不正 /
  禁止列 / remote path / bid-ask不一致 / 空file / 形式不正)
- `DATA_ADAPTER_NOT_CONFIGURED` / `CSV_INTAKE_NOT_PROVIDED` — path未提供

報告はintake category・safe reasons・bar countなどのsafe summaryのみ。
**raw価格・raw spread値・行の中身はdry-run報告に出さない。**

## 5. blocked時の再開条件

blocked理由(safe label)を解消したCSVを再作成し、新しいfresh Stepとして
dry-runを再実行する(同一Step内での場当たり的修正・再試行はしない)。

## 6. dry-run後

- official分類なら: `STRATEGY_BACKTEST_WITH_REAL_DATA_NO_POST`
  (chronological split・OOS温存・spread込み)へ
- 実データ投入時は `treat_as_synthetic_fixture=false` をoperator入力で明示し、
  dataset validation の synthetic-only 制約解除を同Stepでreviewする
- **dry-run成功・backtest実行はいずれもperformance proofではない**
