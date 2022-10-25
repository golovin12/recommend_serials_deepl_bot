import json

from rest_framework.response import Response
from rest_framework.views import APIView


class BotHandler(APIView):
    def post(self, request, bot_type, *args, **kwargs):
        if request.method == 'POST':
            data_request = json.loads(request.body)

            now_bot.process_new_updates(data_request)

            return Response({"ok": 'ok'})