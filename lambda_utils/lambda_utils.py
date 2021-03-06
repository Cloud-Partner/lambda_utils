from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.tracing import Tracer
from os import urandom
import os
import time
import binascii
import json


class Utils:

    def __init__(self):
        self.logger = Logger()
        self.tracer = Tracer()

    def set_trace_id(self, lambda_handler):
        def get_trace_id(raw_trace_id):
            for t in raw_trace_id.split(';'):
                if t.startswith('Root'):
                    return t.split('=')[1]
            return None

        def decorate(event, context):
            if '_X_AMZN_TRACE_ID' in os.environ:
                if get_trace_id(os.environ['_X_AMZN_TRACE_ID']) is not None:
                    os.environ['trace_id'] = get_trace_id(
                        os.environ['_X_AMZN_TRACE_ID'])
            if 'trace_id' not in os.environ:
                START_TIME = time.time()
                HEX = hex(int(START_TIME))[2:]
                os.environ['trace_id'] = "0-{}-{}".format(
                    HEX, str(binascii.hexlify(urandom(12)), 'utf-8'))
            self.logger.structure_logs(
                append=True, trace_id=os.environ['trace_id'])
            self.logger.info(os.environ.get('trace_id'))
            response = lambda_handler(event, context)
            return response
        return decorate

    def api_gateway_response(self, lambda_handler):
        def decorate(event, context):
            response = lambda_handler(event, context)
            if isinstance(response, tuple):
                body = response[0]
                status = response[1]
            else:
                body = response
                status = 200

            if isinstance(body, Exception):
                if status == 200:
                    status = 400
                self.logger.exception(body)
                self.tracer.put_annotation(
                    "ErrorCode", body.__class__.__name__)
                self.tracer.put_annotation(
                    "ErrorMessage", "{}".format(body))
                res = {
                    "isBase64Encoded": False,
                    "statusCode": status,
                    'headers': {
                        "Access-Control-Allow-Origin": "*",
                        "Content-Type": "application/json"
                    },
                    'body': json.dumps({
                        "Code": body.__class__.__name__,
                        "Message": "{}".format(body),
                        "TraceId": os.environ.get('trace_id')
                    })
                }

            else:
                if body is not None and isinstance(body, str) is False:
                    body = json.dumps(body)

                res = {
                    'isBase64Encoded': False,
                    'statusCode': status,
                    'headers': {
                        "Access-Control-Allow-Origin": "*",
                        "Content-Type": "application/json"
                    }
                }
                if body is not None:
                    res['body'] = body
            return res
        return decorate
