"""Modelo documental de Nexo: colaboración con MongoDB Atlas y GridFS."""
from __future__ import annotations

import hashlib
import hmac
import mimetypes
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from gridfs import GridFS
from pymongo import ASCENDING, DESCENDING, MongoClient

MAX_FILE_BYTES = 5 * 1024 * 1024


def now():
    return datetime.now(timezone.utc)


def digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000).hex()


def public(doc):
    if not doc: return None
    return {k:(str(v) if isinstance(v,ObjectId) else v) for k,v in doc.items() if k not in ("password_hash","salt")}


class Store:
    def __init__(self, uri, database="nexo_colabora"):
        if not uri.startswith(("mongodb+srv://","mongodb://")):
            raise ValueError("La URI debe comenzar con mongodb+srv:// o mongodb://")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=8000, appname="NexoColaboraFinalDB")
        self.client.admin.command("ping")
        self.db = self.client[database]
        self.fs = GridFS(self.db)
        self.indexes()

    def indexes(self):
        self.db.users.create_index("username",unique=True)
        self.db.workspaces.create_index("slug",unique=True)
        self.db.memberships.create_index([("workspace_id",ASCENDING),("user_id",ASCENDING)],unique=True)
        self.db.channels.create_index([("workspace_id",ASCENDING),("name",ASCENDING)],unique=True)
        self.db.posts.create_index([("channel_id",ASCENDING),("created_at",DESCENDING)])
        self.db.tasks.create_index([("workspace_id",ASCENDING),("status",ASCENDING)])
        self.db.notifications.create_index([("user_id",ASCENDING),("created_at",DESCENDING)])
        self.db.attachments.create_index([("workspace_id",ASCENDING),("created_at",DESCENDING)])

    def initial_setup_needed(self):
        return self.db.users.count_documents({}) == 0

    def register_owner(self, name, username, password):
        if not self.initial_setup_needed(): raise ValueError("El espacio inicial ya fue creado")
        user = self._create_user(name,username,password)
        ws_id = self.db.workspaces.insert_one({"name":"Estudio Norte","slug":"estudio-norte","description":"Un espacio para hacer avanzar las ideas.","owner_id":user["_id"],"created_at":now()}).inserted_id
        self.db.memberships.insert_one({"workspace_id":ws_id,"user_id":user["_id"],"role":"owner","joined_at":now()})
        channels = {}
        for name,desc in [("General","Novedades y conversación del equipo"),("Diseño","Ideas y revisiones visuales"),("Entregas","Progreso y entregables"),("Recursos","Archivos y material compartido")]:
            channels[name] = self.db.channels.insert_one({"workspace_id":ws_id,"name":name,"description":desc,"created_at":now()}).inserted_id
        examples = [
            ("General","Bienvenidos al espacio","Este centro reúne conversaciones, tareas y archivos del equipo. Cada actualización queda guardada en MongoDB Atlas.","announcement"),
            ("Diseño","Dirección visual de la semana","Trabajaremos con una interfaz enfocada, clara y monocromática. Comparte referencias y comentarios en este canal.","update"),
            ("Entregas","Primera revisión","La estructura del proyecto está lista. El siguiente paso es revisar pendientes y documentar avances.","milestone"),
        ]
        for channel,title,body,kind in examples:
            self.db.posts.insert_one({"workspace_id":ws_id,"channel_id":channels[channel],"author_id":user["_id"],"title":title,"body":body,"kind":kind,"attachments":[],"reactions":[],"created_at":now(),"updated_at":now()})
        for title,status,priority in [("Revisar propuesta visual","todo","high"),("Preparar documentación de datos","doing","medium"),("Validar primera entrega","done","low")]:
            self.db.tasks.insert_one({"workspace_id":ws_id,"channel_id":channels["Entregas"],"title":title,"description":"Tarea de demostración para explorar el tablero.","status":status,"priority":priority,"assignee_id":user["_id"],"author_id":user["_id"],"created_at":now(),"updated_at":now()})
        return public(user)

    def _create_user(self,name,username,password):
        name=name.strip();username=username.strip().lower()
        if len(name)<2 or len(username)<3 or len(password)<8:
            raise ValueError("Escribe nombre, usuario de 3 caracteres y contraseña de 8 caracteres")
        salt=secrets.token_hex(16)
        doc={"name":name,"username":username,"salt":salt,"password_hash":digest(password,salt),"created_at":now()}
        try: doc["_id"]=self.db.users.insert_one(doc).inserted_id
        except Exception as exc:
            if "duplicate key" in str(exc).lower(): raise ValueError("Ese usuario ya existe") from exc
            raise
        return doc

    def login(self,username,password):
        user=self.db.users.find_one({"username":username.strip().lower()})
        if not user or not hmac.compare_digest(user["password_hash"],digest(password,user["salt"])):
            raise ValueError("Usuario o contraseña incorrectos")
        return public(user)

    def invite_member(self,actor_id,workspace_id,name,username,password,role="member"):
        self._require_role(actor_id,workspace_id,("owner",))
        user=self._create_user(name,username,password)
        self.db.memberships.insert_one({"workspace_id":ObjectId(workspace_id),"user_id":user["_id"],"role":role,"joined_at":now()})
        return public(user)

    def _require_member(self,user_id,workspace_id):
        membership=self.db.memberships.find_one({"user_id":ObjectId(user_id),"workspace_id":ObjectId(workspace_id)})
        if not membership: raise PermissionError("No perteneces a este espacio")
        return membership

    def _require_role(self,user_id,workspace_id,roles):
        membership=self._require_member(user_id,workspace_id)
        if membership["role"] not in roles: raise PermissionError("No tienes permisos para esta acción")

    def workspaces(self,user_id):
        ids=[m["workspace_id"] for m in self.db.memberships.find({"user_id":ObjectId(user_id)})]
        return [public(x) for x in self.db.workspaces.find({"_id":{"$in":ids}}).sort("name",1)]

    def create_workspace(self,user_id,name):
        name=name.strip()
        if len(name)<3: raise ValueError("El nombre necesita al menos 3 caracteres")
        slug=(name.lower().replace(" ","-")+"-"+secrets.token_hex(2))
        oid=self.db.workspaces.insert_one({"name":name,"slug":slug,"description":"Espacio de colaboración","owner_id":ObjectId(user_id),"created_at":now()}).inserted_id
        self.db.memberships.insert_one({"workspace_id":oid,"user_id":ObjectId(user_id),"role":"owner","joined_at":now()})
        self.db.channels.insert_one({"workspace_id":oid,"name":"General","description":"Conversación general","created_at":now()})
        return str(oid)

    def channels(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        return [public(x) for x in self.db.channels.find({"workspace_id":ObjectId(workspace_id)}).sort("name",1)]

    def create_channel(self,user_id,workspace_id,name,description=""):
        self._require_member(user_id,workspace_id)
        name=name.strip().lstrip("#")
        if len(name)<2: raise ValueError("El canal necesita al menos 2 caracteres")
        oid=self.db.channels.insert_one({"workspace_id":ObjectId(workspace_id),"name":name,"description":description.strip(),"created_at":now()}).inserted_id
        return str(oid)

    def members(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        memberships=list(self.db.memberships.find({"workspace_id":ObjectId(workspace_id)}))
        users={u["_id"]:u for u in self.db.users.find({"_id":{"$in":[m["user_id"] for m in memberships]}})}
        return [{**public(users[m["user_id"]]),"role":m["role"]} for m in memberships if m["user_id"] in users]

    def posts(self,user_id,workspace_id,channel_id=None,search=""):
        self._require_member(user_id,workspace_id)
        q={"workspace_id":ObjectId(workspace_id),"$or":[
            {"recipient_id":None},{"recipient_id":ObjectId(user_id)},{"author_id":ObjectId(user_id)}]}
        if channel_id: q["channel_id"]=ObjectId(channel_id)
        if search: q["$and"]=[{"$or":[{"title":{"$regex":search,"$options":"i"}},{"body":{"$regex":search,"$options":"i"}}]}]
        docs=list(self.db.posts.find(q).sort("created_at",DESCENDING).limit(100))
        user_ids=list({uid for x in docs for uid in (x["author_id"],x.get("recipient_id")) if uid})
        authors={u["_id"]:u["name"] for u in self.db.users.find({"_id":{"$in":user_ids}})}
        channels={c["_id"]:c["name"] for c in self.db.channels.find({"workspace_id":ObjectId(workspace_id)})}
        counts={x["_id"]:self.db.comments.count_documents({"post_id":x["_id"]}) for x in docs}
        return [{**public(x),"author":authors.get(x["author_id"],"Usuario"),
                 "recipient":authors.get(x.get("recipient_id")) if x.get("recipient_id") else None,
                 "channel":channels.get(x["channel_id"],"Canal"),"comment_count":counts[x["_id"]]} for x in docs]

    def create_post(self,user_id,workspace_id,channel_id,title,body,kind="update",attachment_paths=None,recipient_id=None):
        self._require_member(user_id,workspace_id)
        if recipient_id: self._require_member(recipient_id,workspace_id)
        if not self.db.channels.find_one({"_id":ObjectId(channel_id),"workspace_id":ObjectId(workspace_id)}):
            raise ValueError("Canal no válido")
        title=title.strip();body=body.strip()
        if not title or not body: raise ValueError("Escribe título y contenido")
        if kind not in ("update","announcement","milestone","question"): kind="update"
        attachments=[]
        for path in attachment_paths or []:
            attachments.append(self.add_attachment(user_id,workspace_id,path,recipient_id))
        oid=self.db.posts.insert_one({"workspace_id":ObjectId(workspace_id),"channel_id":ObjectId(channel_id),"author_id":ObjectId(user_id),"recipient_id":ObjectId(recipient_id) if recipient_id else None,"title":title,"body":body,"kind":kind,"attachments":attachments,"reactions":[],"created_at":now(),"updated_at":now()}).inserted_id
        self._notify_members(user_id,workspace_id,"Nueva actualización",title,str(oid),recipient_id)
        return str(oid)

    def _visible_post(self,user_id,workspace_id,post_id):
        self._require_member(user_id,workspace_id)
        post=self.db.posts.find_one({"_id":ObjectId(post_id),"workspace_id":ObjectId(workspace_id)})
        if not post or (post.get("recipient_id") and ObjectId(user_id) not in (post["recipient_id"],post["author_id"])):
            raise ValueError("Publicación no encontrada")
        return post

    def delete_post(self,user_id,workspace_id,post_id):
        post=self._visible_post(user_id,workspace_id,post_id)
        if post["author_id"]!=ObjectId(user_id): self._require_role(user_id,workspace_id,("owner",))
        self.db.comments.delete_many({"post_id":post["_id"]})
        self.db.posts.delete_one({"_id":post["_id"]})

    def add_attachment(self,user_id,workspace_id,path,recipient_id=None):
        self._require_member(user_id,workspace_id)
        if recipient_id: self._require_member(recipient_id,workspace_id)
        path=Path(path)
        if not path.is_file(): raise ValueError("El archivo no existe")
        size=path.stat().st_size
        if size>MAX_FILE_BYTES: raise ValueError("Archivo demasiado grande (máximo 5 MB)")
        mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as stream:
            grid_id=self.fs.put(stream,filename=path.name,content_type=mime,workspace_id=ObjectId(workspace_id),uploader_id=ObjectId(user_id))
        doc={"workspace_id":ObjectId(workspace_id),"grid_id":grid_id,"name":path.name,"mime":mime,"size":size,"uploader_id":ObjectId(user_id),"recipient_id":ObjectId(recipient_id) if recipient_id else None,"created_at":now()}
        return str(self.db.attachments.insert_one(doc).inserted_id)

    def attachments(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        docs=list(self.db.attachments.find({"workspace_id":ObjectId(workspace_id),"$or":[
            {"recipient_id":None},{"recipient_id":ObjectId(user_id)},{"uploader_id":ObjectId(user_id)}]}).sort("created_at",DESCENDING).limit(100))
        users={u["_id"]:u["name"] for u in self.db.users.find({"_id":{"$in":[x["uploader_id"] for x in docs]}})}
        return [{**public(x),"uploader":users.get(x["uploader_id"],"Usuario")} for x in docs]

    def save_attachment(self,user_id,workspace_id,attachment_id,destination):
        _, data = self.read_attachment(user_id,workspace_id,attachment_id)
        with open(destination,"wb") as out:
            out.write(data)

    def read_attachment(self,user_id,workspace_id,attachment_id):
        self._require_member(user_id,workspace_id)
        doc=self.db.attachments.find_one({"_id":ObjectId(attachment_id),"workspace_id":ObjectId(workspace_id)})
        if not doc: raise ValueError("Archivo no encontrado")
        if doc.get("recipient_id") and ObjectId(user_id) not in (doc["recipient_id"],doc["uploader_id"]):
            raise PermissionError("No tienes acceso a este archivo")
        return public(doc), self.fs.get(doc["grid_id"]).read()

    def comments(self,user_id,workspace_id,post_id):
        self._visible_post(user_id,workspace_id,post_id)
        docs=list(self.db.comments.find({"post_id":ObjectId(post_id)}).sort("created_at",ASCENDING))
        users={u["_id"]:u["name"] for u in self.db.users.find({"_id":{"$in":[x["author_id"] for x in docs]}})}
        return [{**public(x),"author":users.get(x["author_id"],"Usuario")} for x in docs]

    def add_comment(self,user_id,workspace_id,post_id,body):
        post=self._visible_post(user_id,workspace_id,post_id)
        body=body.strip()
        if not body: raise ValueError("Escribe un comentario")
        self.db.comments.insert_one({"post_id":post["_id"],"author_id":ObjectId(user_id),"body":body,"created_at":now()})
        if post["author_id"]!=ObjectId(user_id):
            self.db.notifications.insert_one({"user_id":post["author_id"],"workspace_id":ObjectId(workspace_id),"title":"Nuevo comentario","body":post["title"],"related_id":str(post_id),"read":False,"created_at":now()})

    def toggle_reaction(self,user_id,workspace_id,post_id):
        post=self._visible_post(user_id,workspace_id,post_id)
        q={"_id":post["_id"],"workspace_id":ObjectId(workspace_id)}
        uid=ObjectId(user_id)
        self.db.posts.update_one(q,{"$pull":{"reactions":uid}} if uid in post.get("reactions",[]) else {"$addToSet":{"reactions":uid}})

    def tasks(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        docs=list(self.db.tasks.find({"workspace_id":ObjectId(workspace_id)}).sort("created_at",DESCENDING))
        users={u["_id"]:u["name"] for u in self.db.users.find({"_id":{"$in":[x["assignee_id"] for x in docs if x.get("assignee_id")]}})}
        return [{**public(x),"assignee":users.get(x.get("assignee_id"),"Sin asignar")} for x in docs]

    def create_task(self,user_id,workspace_id,channel_id,title,description,assignee_id=None,priority="medium"):
        self._require_member(user_id,workspace_id)
        if not title.strip(): raise ValueError("Escribe un título")
        if assignee_id: self._require_member(assignee_id,workspace_id)
        doc={"workspace_id":ObjectId(workspace_id),"channel_id":ObjectId(channel_id),"title":title.strip(),"description":description.strip(),"status":"todo","priority":priority if priority in ("low","medium","high") else "medium","assignee_id":ObjectId(assignee_id) if assignee_id else None,"author_id":ObjectId(user_id),"created_at":now(),"updated_at":now()}
        oid=self.db.tasks.insert_one(doc).inserted_id
        if assignee_id and assignee_id!=user_id:
            self.db.notifications.insert_one({"user_id":ObjectId(assignee_id),"workspace_id":ObjectId(workspace_id),"title":"Nueva tarea asignada","body":title,"related_id":str(oid),"read":False,"created_at":now()})
        return str(oid)

    def set_task_status(self,user_id,workspace_id,task_id,status):
        self._require_member(user_id,workspace_id)
        if status not in ("todo","doing","done"): raise ValueError("Estado inválido")
        self.db.tasks.update_one({"_id":ObjectId(task_id),"workspace_id":ObjectId(workspace_id)},{"$set":{"status":status,"updated_at":now()}})

    def notifications(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        return [public(x) for x in self.db.notifications.find({"user_id":ObjectId(user_id),"workspace_id":ObjectId(workspace_id)}).sort("created_at",DESCENDING).limit(30)]

    def mark_read(self,user_id,workspace_id):
        self._require_member(user_id,workspace_id)
        self.db.notifications.update_many({"user_id":ObjectId(user_id),"workspace_id":ObjectId(workspace_id)},{"$set":{"read":True}})

    def _notify_members(self,actor_id,workspace_id,title,body,related_id,recipient_id=None):
        recipients=[m["user_id"] for m in self.db.memberships.find({"workspace_id":ObjectId(workspace_id),"user_id":{"$ne":ObjectId(actor_id)}})]
        if recipient_id: recipients=[uid for uid in recipients if uid==ObjectId(recipient_id)]
        if recipients:self.db.notifications.insert_many([{"user_id":uid,"workspace_id":ObjectId(workspace_id),"title":title,"body":body,"related_id":related_id,"read":False,"created_at":now()} for uid in recipients])
