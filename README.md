# コーシャハイム千石 空室通知

JKKねっとを約5分ごとに確認し、コーシャハイム千石に新しい募集住戸が出たときだけAndroidへ通知します。

通知には部屋番号、間取り、家賃、共益費を表示します。同じ住戸について5分ごとに繰り返し通知することはありません。通知をタップするとJKKねっとを開きます。

## 用意するもの

- Androidスマートフォン
- 最初の設定に使うPC
- 無料のGitHubアカウント
- Android版ntfyアプリ

追加のサーバーや常時起動PCは不要です。

## 重要：GitHubリポジトリはPublicにする

5分ごとの実行は月に約8,640回になります。Privateリポジトリでは無料枠を超える可能性が高いため、無料運用する場合はPublicリポジトリを使ってください。この一式に氏名・住所・JKKのログイン情報は入りません。通知先のトピック名だけはGitHubのSecretに保存し、公開ファイルには書きません。

## 1. Androidでntfyを設定する

1. Google Playで「ntfy」をインストールします。
2. 推測されにくいトピック名を自分で作ります。例：`jkk-sengoku-`の後ろに英数字を24文字以上付けます。
3. ntfyアプリで「＋」→トピック名を入力→購読します。
4. Androidの設定でntfyの通知を許可します。

ntfy.shの公開トピックは、トピック名を知っている人が通知を読める仕組みです。氏名などを含めず、必ず長くランダムな名前にしてください。

## 2. GitHubへファイルを置く

1. GitHubにログインし、右上の「＋」→「New repository」を開きます。
2. Repository nameを `jkk-sengoku-watcher` にします。
3. 「Public」を選びます。
4. 「Add a README file」はオフのまま「Create repository」を押します。
5. 作成後に「uploading an existing file」を押します。
6. このZIPを展開し、`jkk-sengoku-watcher`フォルダの**中身をすべて**アップロードします。`.github`フォルダも必要です。
7. 画面下部の「Commit changes」を押します。

アップロード後、GitHub上に少なくとも次が見えれば成功です。

- `.github/workflows/check-vacancy.yml`
- `.github/workflows/keepalive.yml`
- `jkk_watcher.py`
- `state.json`

## 3. 通知先をSecretに登録する

1. 作成したリポジトリの「Settings」を開きます。
2. 左側の「Secrets and variables」→「Actions」を開きます。
3. 「New repository secret」を押します。
4. Nameに `NTFY_TOPIC` と入力します。
5. Secretに手順1で作ったntfyのトピック名を入力します。
6. 「Add secret」を押します。

## 4. テスト通知を送る

1. リポジトリ上部の「Actions」を開きます。
2. 必要なら「I understand my workflows, go ahead and enable them」を押します。
3. 左側の「Check JKK vacancy」を選びます。
4. 「Run workflow」を押します。
5. 「Androidへテスト通知だけを送る」にチェックを入れて実行します。
6. Androidに「JKK空室通知（テスト）」が届けば通知設定は完了です。

続けて、チェックを外した状態でもう一度「Run workflow」を実行してください。これで現在の空室状況が初期状態として保存されます。現在すでに募集住戸がある場合は、その住戸も通知されます。

## 5. 正常動作を確認する

「Actions」→最新の「Check JKK vacancy」を開き、緑色のチェックが付いていれば正常です。以後は毎時3、8、13…58分ごろに自動確認します。

GitHub Actionsの定期実行は混雑時に遅れることがあり、厳密な5分間隔は保証されません。

## 通知を止める方法

リポジトリの「Actions」→「Check JKK vacancy」→右上の「…」→「Disable workflow」を押します。完全に不要になった場合はリポジトリを削除しても構いません。

## 仕組みと注意点

- JKKねっとの公開検索画面だけを確認し、ログインや自動申込みは行いません。
- 通常は5分に1回、空室があるときのみ詳細取得を数回行います。
- JKKねっとの画面構造が変わると、誤通知せず処理をエラー終了します。Actionsが赤色になった場合はコード修正が必要です。
- JKK公式情報を最終確認のうえ、ご自身で申込みを行ってください。
- GitHubの仕様上、Publicリポジトリは60日間活動がないと定期実行が無効化されることがあります。その対策として月1回だけ`last_activity.txt`を自動更新します。

## PC上での確認（任意）

Python 3が入っている場合、フォルダ内で以下を実行すると、通知せず現在の募集戸数だけを確認できます。

```bash
python jkk_watcher.py --dry-run
```

テストは次で実行できます。

```bash
python -m unittest discover -s tests -v
```
