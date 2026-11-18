"""Consultas de agregación para explicar el modelo documental en clase."""
import os
from app import read_env
from pymongo import MongoClient

read_env()
uri=os.getenv("MONGODB_URI")
if not uri:raise SystemExit("Primero conecta Nexo para crear .env")
db=MongoClient(uri)[os.getenv("MONGODB_DATABASE","nexo_colabora")]

print("Publicaciones por canal:")
for row in db.posts.aggregate([
    {"$group":{"_id":"$channel_id","publicaciones":{"$sum":1}}},
    {"$lookup":{"from":"channels","localField":"_id","foreignField":"_id","as":"canal"}},
    {"$unwind":"$canal"},
    {"$project":{"_id":0,"canal":"$canal.name","publicaciones":1}},
    {"$sort":{"publicaciones":-1}},
]):print(row)

print("\nTareas por estado:")
for row in db.tasks.aggregate([{"$group":{"_id":"$status","cantidad":{"$sum":1}}},{"$sort":{"_id":1}}]):print(row)

print("\nArchivos por tipo MIME:")
for row in db.attachments.aggregate([{"$group":{"_id":"$mime","cantidad":{"$sum":1},"bytes":{"$sum":"$size"}}},{"$sort":{"cantidad":-1}}]):print(row)
