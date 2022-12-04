import asyncio
import sys
import tornado.web
import tornado.escape
import os

from aio_pika import Message, connect_robust

settings = {
    "debug": False,
    "template_path": os.path.join(os.path.realpath(".."), "frontend"),
    "static_path": os.path.join(os.path.realpath(".."), "frontend/static"),
}


class Base:
    QUEUE: asyncio.Queue


class IndexHandler(tornado.web.RequestHandler):
    async def get(self) -> None:
        await self.render("index.html")


class PublisherHandler(tornado.web.RequestHandler):
    async def post(self) -> None:
        connection = self.application.settings["amqp_connection"]
        channel = await connection.channel()
        try:
            await channel.default_exchange.publish(
                Message(body=self.request.body), routing_key="user_feedback",
            )
        finally:
            await channel.close()

        await self.finish("OK")


async def make_app() -> tornado.web.Application:
    amqp_connection = await connect_robust(os.environ["RABBITMQ_CONNECTION"])

    return tornado.web.Application(
        [(r"/publish", PublisherHandler), (r"/", IndexHandler)],
        amqp_connection=amqp_connection, **settings
    )


async def main() -> None:
    app = await make_app()
    app.listen(80, "0.0.0.0")
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
