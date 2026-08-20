from flask_restful import Resource
from flask import request


class StockResources(Resource):
    def get(self):
        reqst = request.args
        print(reqst)
        return {'hello': 'world'}

    def post(self):
        rq = request.form
        print(rq)

        return {'hello': 'world'}

    def put(self):
        return {'hello': 'world'}

    def delete(self):
        return {'hello': 'world'}
