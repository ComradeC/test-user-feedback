import asyncio
import os

import sqlalchemy
import databases

from pydantic import BaseModel
from aio_pika import connect_robust
from aio_pika.abc import AbstractIncomingMessage
from fastapi import FastAPI

app = FastAPI()
DATABASE_URL = os.environ["DATABASE_URL"]
database = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()
user_feedback = sqlalchemy.Table(
    "user_feedback",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("firstName", sqlalchemy.String),
    sqlalchemy.Column("surname", sqlalchemy.String),
    sqlalchemy.Column("patronymic", sqlalchemy.String),
    sqlalchemy.Column("phone", sqlalchemy.VARCHAR),
    sqlalchemy.Column("message", sqlalchemy.String),
)

engine = sqlalchemy.create_engine(DATABASE_URL)
metadata.create_all(engine)


class InputMessage(BaseModel):
    firstName: str
    surname: str
    patronymic: str
    phone: str
    messageText: str


class Message(BaseModel):
    id: int
    firstName: str
    surname: str
    patronymic: str
    phone: str
    messageText: str


@app.on_event("startup")
async def startup():
    await database.connect()

    rabbit_conn = await connect_robust(os.environ["RABBITMQ_CONNECTION"])
    async with rabbit_conn:
        channel = await rabbit_conn.channel()
        queue = await channel.declare_queue("user_feedback")
        await queue.consume(on_message, no_ack=True)
        print(" [*] Waiting for messages. To exit press CTRL+C")
        await asyncio.Future()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


async def on_message(message: AbstractIncomingMessage) -> None:
    print("Siphon: got message:", message.body)
    await create_message(InputMessage.parse_raw(message.body))


@app.post("/newMessage/", response_model=Message)
async def create_message(message: InputMessage):
    query = user_feedback.insert().values(firstName=message.firstName,
                                          surname=message.surname,
                                          patronymic=message.patronymic,
                                          phone=message.phone,
                                          message=message.messageText)
    last_record_id = await database.execute(query)
    return {**message.dict(), "id": last_record_id}
