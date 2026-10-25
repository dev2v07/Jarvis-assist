from core.agent_base import Agent
import uuid


class MainAgent(Agent):

    def __init__(self, bus, app):

        super().__init__("main", bus)

        self.app = app

        # msg_id -> asyncio.Future
        self.pending = {}

    # --------------------------------------------------
    # handle messages
    # --------------------------------------------------

    async def handle_message(self, msg):

        msg_type = msg.get("type")
        payload = msg.get("payload", {})

        # ---------------------------------------
        # шаг начался
        # ---------------------------------------

        if msg_type == "step_started":

            step = payload.get("step")
            index = payload.get("index")
            total = payload.get("total")

            if index and total:
                print(f"▶ [{index}/{total}] {step}")
            else:
                print(f"▶ Выполняется шаг: {step}")

            return

        # ---------------------------------------
        # шаг завершён
        # ---------------------------------------

        if msg_type == "step_finished":

            step = payload.get("step")
            result = payload.get("result")

            print(f"✔ Шаг выполнен: {step}")

            if result:
                print(result)

            return

        # ---------------------------------------
        # финальный результат (CriticAgent)
        # ---------------------------------------

        if msg_type in ("review_result", "final_response"):

            msg_id = payload.get("original_msg_id")
            result = payload.get("result")

            if msg_id in self.pending:

                future = self.pending[msg_id]

                if not future.done():
                    future.set_result(result)

                del self.pending[msg_id]

            return

        # ---------------------------------------
        # ошибка выполнения
        # ---------------------------------------

        if msg_type == "request_failed":

            msg_id = payload.get("original_msg_id")
            error = payload.get("error")

            if msg_id in self.pending:

                future = self.pending[msg_id]

                if not future.done():
                    future.set_result(f"Ошибка: {error}")

                del self.pending[msg_id]

            return

        # ---------------------------------------
        # неизвестный тип
        # ---------------------------------------

        print(f"[MainAgent] неизвестный тип сообщения: {msg_type}")