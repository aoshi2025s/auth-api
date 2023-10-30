from fastapi import FastAPI,HTTPException,status,Depends
from fastapi.exception_handlers import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine,Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker,Session
from pydantic import BaseModel,Field
from typing import Optional
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import base64
from passlib.context import CryptContext

DATABASE_URL = "sqlite:///./auth.db"

#データベースと接続
engine = create_engine(
    DATABASE_URL,connect_args={"check_same_thread":False})

sessionLocal = sessionmaker(bind=engine,autocommit=False,autoflush=False)

#エンジンを作成した後にマッピングを宣言
Base = declarative_base()

def get_db():
    """
    SessionLocal()の作成とリクエストの処理をtry文に記述
    finallyブロックでデータベースセッションを閉じる
    リクエスト後にデータベースセッションが常に閉じられるようにしつつ、
    リクエストの処理中に例外が発生した場合も閉じる
    """
    db = sessionLocal()

    try:
        yield db
    finally:
        db.close()

class UserIn(BaseModel):
    user_id: str = Field(...,min_length=6,max_length=20,pattern="^[a-zA-Z0-9]*$")
    password: str = Field(...,min_length=8,max_length=20,pattern="^[\\x21-\\x7e]*$")
    nickname: Optional[str] = Field(None,min_length=0,max_length=30)
    comment: Optional[str] = Field(None,min_length=0,max_length=100)

#空白と制御コードを除くASCII文字＝＞"^[\\x21-\\x7e]*$"

class patchUser(BaseModel):
    nickname: Optional[str] = Field(None,min_length=0,max_length=30,pattern="^[^\x00-\x1f\x7f-\x9f]*$")
    comment: Optional[str] = Field(None,min_length=0,max_length=100,pattern="^[^\x00-\x1f\x7f-\x9f]*$")
    user_id: Optional[str] = None
    password: Optional[str] = None

    class Config:
        orm_mode = True

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(String(20),nullable=False)
    password = Column(String(20),nullable=False)
    nickname = Column(String,nullable=True)
    comment = Column(String(100),nullable=True)

pwd_context = CryptContext(
    schemes = ["bcrypt"],
    deprecated = "auto",
)

class Hash():
    @staticmethod
    def bcrypt(password: str):
        return pwd_context.hash(password)
    
    @staticmethod
    def verify(hashed_password,plain_password):
        """
        このコードでは、Hashクラスにverifyメソッドを追加しています。
        このメソッドは、passlibライブラリのCryptContextを使用して、
        ハッシュ化されたパスワードと平文のパスワードが一致するかどうかを確認します。
        もし一致すれば、メソッドはTrueを返し、一致しなければFalseを返します。
        """
        return pwd_context.verify(plain_password,hashed_password)

app = FastAPI()

security = HTTPBasic()

@app.get("/")
def index():
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message":"hello"}
    )

#HTTPExceptionのためのカスタムハンドラを定義
@app.exception_handler(HTTPException)
def custom_http_exception_handler(request,exc):
    return JSONResponse(content=exc.detail,status_code=exc.status_code)

#バリデーションエラー
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request,exc):

    if exc.errors()[0]["type"] == "string_too_short":
        error_cause = "length is too short"
    elif exc.errors()[0]["type"] == "string_too_long":
        error_cause = "length is too long"
    elif exc.errors()[0]["type"] == "string_pattern_mismatch":
        error_cause = "pattern is not match"
    elif exc.errors()[0]["type"] == "missing":
        error_cause = "required user_id and password"
    else:
        error_cause = exc.errors()
    return JSONResponse(
        status_code = 400,
        content = {
            "message":"Account creation failed",
            "cause":error_cause},
    )

def authenticate(credentials: HTTPBasicCredentials=Depends(security),db: Session=Depends(get_db)):
    response_message = "Authentication Failed"
    user = db.query(UserDB).filter(UserDB.user_id == credentials.username).first()
    if not user or not Hash.verify(user.password,credentials.password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = {"message": response_message},
            headers = {"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.post("/signup",status_code=status.HTTP_201_CREATED,tags=["users"])
def create_user(request: UserIn, db:Session = Depends(get_db)):
    response_message = "Account successfully created"

    new_user = UserDB(
        user_id = request.user_id,
        password = Hash.bcrypt(request.password),
        nickname = request.nickname,
        comment = request.comment)
    
    user = db.query(UserDB).filter(UserDB.user_id == request.user_id).first()
    if user:
        response_message = "Account creation failed"
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = {
                "message":response_message,
                "cause":"already same user_id is used"
            }
        )
    
    if not new_user.nickname:
        new_user.nickname = new_user.user_id
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_response = {}
    user_response["user_id"] = new_user.user_id
    user_response["nickname"] = new_user.nickname
    if new_user.comment:
        user_response["comment"] = new_user.comment

    return {
        "message":response_message,
        "user" : user_response
    }

#usersのデータベース情報すべて取得
"""
@app.get("/users",tags=["users"])
def all_fetch(db:Session = Depends(get_db)):
    users = db.query(UserDB).all()
    return users
"""


@app.get("/users/{user_id}",status_code=status.HTTP_200_OK,tags=["users"])
def show_user(user_id: str, db:Session=Depends(get_db),username: str = Depends(authenticate)):
    if username != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message":"Authentication Failed"}
        )
    user = db.query(UserDB).filter(UserDB.user_id==user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail= {"message":"No User found"}
        )
    if user.nickname == "":
        user.nickname = user_id
    user_response = {}

    user_response["user_id"] = user_id
    user_response["nickname"] = user.nickname
    if user.comment:
        user_response["comment"] = user.comment
    
    return {
        "message":"User details by user_id",
        "user":user_response
    }

@app.patch("/users/{user_id}",status_code=status.HTTP_200_OK,tags=["users"])
def update_user(user_id: str,request: patchUser,db:Session=Depends(get_db),username: str = Depends(authenticate)):
    if username != user_id:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail = {"message":"No Permission for Update"}
        )
    user = db.query(UserDB).filter(UserDB.user_id==user_id).first()
    if not user:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = {"message":"No User found"}
        )
    #リクエストボディを検証
    if request.nickname == "" or request.comment == "":
        pass
    elif not request.nickname and not request.comment:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = {
                "message":"User updation failed",
                "cause":"required nickname or comment"
            }
        )
    if request.user_id or request.password:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = {
                "message":"User updation failed",
                "cause":"not updatable user_id and password"
            }
        )

    patched_user = {}
    if request.nickname:
        user.nickname = request.nickname
        patched_user["nickname"] = user.nickname
    if request.nickname == "":
        user.nickname = user_id
        patched_user["nickname"] = user.nickname
    if request.comment or request.comment == "":
        user.comment = request.comment
        patched_user["comment"] = user.comment

    db.commit()
    return {
        "message":"User successfully updated",
        "recipe":[patched_user]
    }


@app.post("/close",status_code=status.HTTP_200_OK,tags=["users"])
def delete_user(db: Session=Depends(get_db),username: str = Depends(authenticate)):
    user = db.query(UserDB).filter(UserDB.user_id == username)
    user.delete(synchronize_session=False)
    db.commit()

    return {
        "message":"Account and user successfully removed"
    }


Base.metadata.create_all(engine)