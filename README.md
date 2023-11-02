# auth-api
# アカウント認証api
ユーザ名とパスワードでアカウントを認証できるapiを作りました
heroku,dataspace,renderにデプロイしました。
urlの最後に"/docs"とつけるとこのapiのswaggerUIが見れます。
デフォルトのurlにアクセスすると、{"message":"hello"}を返します。

# heroku

https://track-heroku-app-0025927817d9.herokuapp.com/

# dataspace
urlにアクセスするには、data spaceへのログインが必要になります。
デプロイは一番簡単だったのですが、アクセスにログインの必要がない他のデプロイサービスを探しました。

https://authapi-1-w4762713.deta.app/docs#/

# render
無料枠なので、アクセスして数分後に起動するようです。

https://auth-api-render.onrender.com

# デプロイ方法
上記3つのサービスに共通しているのは、requirements.txtの中に、pythonの必要なライブラリ名を書いておくということです。
herokuではその他にProcfileという名前のファイルに起動オプションを書きました。
```powershell
web:  uvicorn main:app --reload --host=0.0.0.0 --port=${PORT:-5000}
```
renderでは、起動オプションを記述する場所(Settingsの、StartCommandという箇所)があったので、その箇所に以下の文を書きました。
```powershell
uvicorn main:app --reload --host=0.0.0.0 --port=${PORT:-5000}
```
