"""Nexo — centro de colaboración de escritorio conectado a MongoDB Atlas."""
from __future__ import annotations

import os
import secrets
import threading
import tkinter as tk
from io import BytesIO
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from store import Store

ROOT=Path(__file__).resolve().parent
ENV=ROOT/".env"


def read_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key,value=line.split("=",1)
                os.environ.setdefault(key.strip(),value.strip())


def short_date(value):
    try:return value.astimezone().strftime("%d %b · %H:%M")
    except Exception:return "Ahora"


class Nexo(ctk.CTk):
    def __init__(self):
        read_env()
        super().__init__()
        self.title("Nexo — Centro de colaboración")
        self.geometry("1320x820")
        self.minsize(980,650)
        self.theme="dark"
        self.set_theme("dark")
        self.store=None;self.user=None;self.workspace=None;self.channel=None;self.tab="updates";self.search=""
        self.show_connect()

    def set_theme(self,mode):
        self.theme=mode
        ctk.set_appearance_mode(mode)
        if mode=="dark":
            self.colors={"bg":"#080909","sidebar":"#101111","surface":"#141515","surface2":"#1c1d1d","border":"#303232","text":"#f5f5f3","muted":"#989b9a","button":"#f5f5f3","button_text":"#111212","hover":"#262828"}
        else:
            self.colors={"bg":"#f3f3f2","sidebar":"#e9e9e7","surface":"#ffffff","surface2":"#ededeb","border":"#d7d7d4","text":"#171818","muted":"#777a78","button":"#161717","button_text":"#ffffff","hover":"#e0e0de"}
        self.configure(fg_color=self.colors["bg"])

    def clear(self):
        for child in self.winfo_children():child.destroy()

    def label(self,parent,text,size=12,weight="normal",color=None,**kwargs):
        return ctk.CTkLabel(parent,text=text,font=("Segoe UI",size,weight),text_color=color or self.colors["text"],**kwargs)

    def btn(self,parent,text,command,solid=False,width=100,height=34,**kwargs):
        return ctk.CTkButton(parent,text=text,command=command,width=width,height=height,corner_radius=8,
            fg_color=self.colors["button"] if solid else self.colors["surface2"],
            text_color=self.colors["button_text"] if solid else self.colors["text"],
            hover_color=self.colors["muted"] if solid else self.colors["hover"],font=("Segoe UI",12,"bold"),**kwargs)

    def frame(self,parent,fg=None,**kwargs):
        return ctk.CTkFrame(parent,fg_color=fg or self.colors["surface"],corner_radius=10,
            border_width=1,border_color=self.colors["border"],**kwargs)

    def entry(self,parent,placeholder="",show=None):
        return ctk.CTkEntry(parent,placeholder_text=placeholder,show=show,width=330,height=38,corner_radius=8,
            fg_color=self.colors["surface2"],border_color=self.colors["border"],text_color=self.colors["text"])

    def show_connect(self):
        self.clear()
        wrap=ctk.CTkFrame(self,fg_color="transparent")
        wrap.place(relx=.5,rely=.5,anchor="center")
        self.label(wrap,"◈  NEXO",16,"bold").pack(pady=(0,45))
        box=self.frame(wrap)
        box.pack(ipadx=34,ipady=29)
        self.label(box,"Conecta tu espacio",28,"bold").pack(anchor="w",padx=30,pady=(10,8))
        self.label(box,"Usa la cadena de conexión de tu cuenta de MongoDB Atlas.",12,color=self.colors["muted"]).pack(anchor="w",padx=30,pady=(0,25))
        self.label(box,"MONGODB URI",10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=30)
        uri=self.entry(box,"mongodb+srv://usuario:contraseña@cluster...")
        uri.configure(width=440,show="•")
        uri.pack(padx=30,pady=(7,15))
        if os.getenv("MONGODB_URI"):uri.insert(0,os.environ["MONGODB_URI"])
        status=self.label(box,"La contraseña se guarda solo en tu archivo .env local.",11,color=self.colors["muted"])
        status.pack(anchor="w",padx=30,pady=(0,15))
        def connect():
            value=uri.get().strip()
            if not value:status.configure(text="Pega la URI de Atlas para continuar");return
            status.configure(text="Conectando con Atlas…")
            button.configure(state="disabled")
            def work():
                try:store=Store(value,os.getenv("MONGODB_DATABASE","nexo_colabora"))
                except Exception as exc:self.after(0,lambda:self.connection_error(status,button,str(exc)))
                else:self.after(0,lambda:self.connection_ready(store,value))
            threading.Thread(target=work,daemon=True).start()
        button=self.btn(box,"Conectar a MongoDB Atlas  →",connect,solid=True,width=440,height=42)
        button.pack(padx=30,pady=(0,10))
        self.label(wrap,"NEXO / PROYECTO FINAL DE BASES DE DATOS",10,"bold",color=self.colors["muted"]).pack(pady=32)
        if os.getenv("MONGODB_URI"):
            self.after(150,connect)

    def connection_error(self,status,button,error):
        button.configure(state="normal")
        status.configure(text="No se pudo conectar. Revisa usuario, contraseña y acceso de red.")
        messagebox.showerror("Conexión a Atlas",error)

    def connection_ready(self,store,uri):
        self.store=store
        ENV.write_text("MONGODB_URI="+uri+"\nMONGODB_DATABASE="+os.getenv("MONGODB_DATABASE","nexo_colabora")+"\n",encoding="utf-8")
        if store.initial_setup_needed():self.show_auth(first=True)
        else:self.show_auth(first=False)

    def show_auth(self,first=False):
        self.clear()
        wrap=ctk.CTkFrame(self,fg_color="transparent")
        wrap.place(relx=.5,rely=.5,anchor="center")
        self.label(wrap,"◈  NEXO",16,"bold").pack(pady=(0,35))
        box=self.frame(wrap);box.pack(ipadx=35,ipady=27)
        self.label(box,"Crea tu espacio" if first else "Bienvenido de nuevo",28,"bold").pack(anchor="w",padx=30,pady=(5,7))
        self.label(box,"Tu centro de colaboración, en un solo lugar." if first else "Ingresa para continuar con tu equipo.",12,color=self.colors["muted"]).pack(anchor="w",padx=30,pady=(0,22))
        name=None
        if first:
            name=self.entry(box,"Tu nombre");name.pack(padx=30,pady=5)
        username=self.entry(box,"Usuario");username.pack(padx=30,pady=5)
        password=self.entry(box,"Contraseña",show="•");password.pack(padx=30,pady=5)
        def submit():
            try:
                self.user=self.store.register_owner(name.get(),username.get(),password.get()) if first else self.store.login(username.get(),password.get())
                self.enter_app()
            except Exception as exc:messagebox.showerror("Acceso",str(exc))
        self.btn(box,"Crear cuenta y entrar  →" if first else "Entrar al espacio  →",submit,solid=True,width=330,height=42).pack(padx=30,pady=(20,5))
        password.bind("<Return>",lambda _:submit())

    def enter_app(self):
        spaces=self.store.workspaces(self.user["_id"])
        if not spaces:messagebox.showerror("Espacios","No tienes acceso a ningún espacio");return
        self.workspace=spaces[0]
        self.channel=None
        self.tab="updates"
        self.render_app()

    def render_app(self):
        self.clear();c=self.colors
        self.role=self.store.workspace_role(self.user["_id"],self.workspace["_id"])
        top=ctk.CTkFrame(self,fg_color=c["sidebar"],height=59,corner_radius=0)
        top.pack(fill="x");top.pack_propagate(False)
        self.label(top,"◈",23,"bold").pack(side="left",padx=(22,8))
        self.label(top,"NEXO",15,"bold").pack(side="left")
        self.label(top,"  /  "+self.workspace["name"],12,color=c["muted"]).pack(side="left",padx=11)
        self.btn(top,"◐",self.toggle_theme,width=36).pack(side="right",padx=(0,16),pady=12)
        self.btn(top,"◌",self.show_notifications,width=36).pack(side="right",padx=7,pady=12)
        self.btn(top,"+  Nueva actualización",self.compose_post,solid=True,width=176).pack(side="right",padx=8,pady=12)
        body=ctk.CTkFrame(self,fg_color=c["bg"],corner_radius=0);body.pack(fill="both",expand=True)
        sidebar=ctk.CTkFrame(body,fg_color=c["sidebar"],width=225,corner_radius=0);sidebar.pack(side="left",fill="y");sidebar.pack_propagate(False)
        spaces=self.store.workspaces(self.user["_id"])
        self.label(sidebar,"ESPACIOS",10,"bold",color=c["muted"]).pack(anchor="w",padx=19,pady=(25,9))
        for ws in spaces:
            self.side_button(sidebar,"▣   "+ws["name"],lambda x=ws:self.change_workspace(x),ws["_id"]==self.workspace["_id"])
        if self.role=="owner":self.side_button(sidebar,"+   Nuevo espacio",self.create_workspace)
        self.label(sidebar,"CANALES",10,"bold",color=c["muted"]).pack(anchor="w",padx=19,pady=(30,9))
        self.side_button(sidebar,"⌗   Todos",lambda:self.change_channel(None),self.channel is None)
        for ch in self.store.channels(self.user["_id"],self.workspace["_id"]):
            self.side_button(sidebar,"#   "+ch["name"],lambda x=ch:self.change_channel(x),self.channel and ch["_id"]==self.channel["_id"])
        if self.role=="owner":self.side_button(sidebar,"+   Crear canal",self.create_channel)
        spacer=ctk.CTkFrame(sidebar,fg_color="transparent");spacer.pack(fill="both",expand=True)
        account=self.frame(sidebar,fg=c["surface2"]);account.pack(fill="x",padx=10,pady=12)
        self.label(account,"◯",23).pack(side="left",padx=(10,7),pady=8)
        self.label(account,self.user["name"],11,"bold").pack(side="left")
        self.label(account,"ADMIN" if self.role=="owner" else "USUARIO",8,"bold",color=c["muted"]).pack(side="left",padx=4)
        self.btn(account,"↪",self.logout,width=30,height=28).pack(side="right",padx=7)
        self.btn(account,"⚙",self.change_password,width=30,height=28).pack(side="right",padx=2)
        main=ctk.CTkFrame(body,fg_color=c["bg"],corner_radius=0);main.pack(side="left",fill="both",expand=True)
        header=ctk.CTkFrame(main,fg_color="transparent",height=105);header.pack(fill="x",padx=30,pady=(24,8))
        self.label(header,"WORKSPACE  /  "+(self.channel["name"].upper() if self.channel else "TODOS LOS CANALES"),10,"bold",color=c["muted"]).pack(anchor="w")
        self.label(header,self.channel["name"] if self.channel else "Tu centro de colaboración",27,"bold").pack(anchor="w",pady=(7,0))
        tabs=ctk.CTkFrame(main,fg_color="transparent",height=42);tabs.pack(fill="x",padx=30,pady=(0,12))
        for key,title in [("updates","Actualizaciones"),("tasks","Tareas"),("files","Archivos"),("members","Personas")]:
            self.btn(tabs,title,lambda k=key:self.change_tab(k),solid=self.tab==key,width=110,height=32).pack(side="left",padx=(0,7))
        self.content=ctk.CTkFrame(main,fg_color="transparent");self.content.pack(fill="both",expand=True,padx=30,pady=(0,24))
        self.render_content()

    def side_button(self,parent,text,command,active=False):
        c=self.colors
        self.btn(parent,text,command,solid=active,width=199,height=37,anchor="w").pack(padx=12,pady=2)

    def toggle_theme(self):
        self.set_theme("light" if self.theme=="dark" else "dark");self.render_app()

    def logout(self):self.user=None;self.show_auth(False)
    def change_password(self):
        def submit(v):
            if v["new"]!=v["confirm"]:raise ValueError("Las nuevas contraseñas no coinciden")
            self.store.change_password(self.user["_id"],v["current"],v["new"])
            messagebox.showinfo("Contraseña","Tu contraseña se actualizó correctamente")
        self.dialog("Cambiar contraseña",[("current","CONTRASEÑA ACTUAL","Contraseña actual",True),
            ("new","NUEVA CONTRASEÑA","Mínimo 10 caracteres",True),
            ("confirm","CONFIRMAR","Repite la nueva contraseña",True)],submit,"Actualizar contraseña")
    def change_workspace(self,workspace):self.workspace=workspace;self.channel=None;self.tab="updates";self.render_app()
    def change_channel(self,channel):self.channel=channel;self.tab="updates";self.render_app()
    def change_tab(self,tab):self.tab=tab;self.render_app()

    def render_content(self):
        for child in self.content.winfo_children():child.destroy()
        if self.tab=="updates":self.render_updates()
        elif self.tab=="tasks":self.render_tasks()
        elif self.tab=="files":self.render_files()
        else:self.render_members()

    def render_updates(self):
        c=self.colors
        toolbar=ctk.CTkFrame(self.content,fg_color="transparent");toolbar.pack(fill="x",pady=(0,15))
        search=self.entry(toolbar,"⌕   Buscar actualizaciones...")
        search.configure(width=290);search.pack(side="left")
        if self.search:search.insert(0,self.search)
        def search_now(_=None):self.search=search.get().strip();self.render_content()
        search.bind("<Return>",search_now)
        self.btn(toolbar,"Buscar",search_now,width=72).pack(side="left",padx=7)
        self.btn(toolbar,"Actualizar ↻",self.render_content,width=103).pack(side="right")
        feed=ctk.CTkScrollableFrame(self.content,fg_color="transparent");feed.pack(fill="both",expand=True)
        posts=self.store.posts(self.user["_id"],self.workspace["_id"],self.channel["_id"] if self.channel else None,self.search)
        if not posts:self.label(feed,"Aún no hay actualizaciones. Publica la primera.",15,color=c["muted"]).pack(pady=70)
        for index,p in enumerate(posts):
            card=self.frame(feed);card.grid(row=index//2,column=index%2,sticky="nsew",padx=(0,12) if index%2==0 else (0,0),pady=(0,12))
            feed.grid_columnconfigure(0,weight=1,uniform="post");feed.grid_columnconfigure(1,weight=1,uniform="post")
            head=ctk.CTkFrame(card,fg_color="transparent");head.pack(fill="x",padx=18,pady=(17,12))
            self.label(head,"◯",22).pack(side="left",padx=(0,8))
            self.label(head,p["author"],12,"bold").pack(side="left")
            self.label(head,"  ·  #"+p["channel"]+("  →  "+p["recipient"] if p.get("recipient") else "")+"  ·  "+short_date(p["created_at"]),10,color=c["muted"]).pack(side="left")
            self.label(card,p["title"],17,"bold",wraplength=390,justify="left").pack(anchor="w",padx=18)
            self.label(card,p["body"][:360],12,color=c["muted"],wraplength=400,justify="left").pack(anchor="w",padx=18,pady=(8,17))
            if p.get("attachments"):
                self.label(card,"⌁  "+str(len(p["attachments"]))+" archivo(s) adjunto(s)",11,color=c["muted"]).pack(anchor="w",padx=18,pady=(0,8))
            foot=ctk.CTkFrame(card,fg_color="transparent");foot.pack(fill="x",padx=14,pady=(0,12))
            self.btn(foot,"♡  "+str(len(p.get("reactions",[]))),lambda x=p:self.react(x),width=67,height=27).pack(side="left",padx=3)
            self.btn(foot,"◌  "+str(p["comment_count"]),lambda x=p:self.open_comments(x),width=67,height=27).pack(side="left",padx=3)
            self.btn(foot,"Abrir →",lambda x=p:self.open_post(x),width=72,height=27).pack(side="right",padx=3)

    def render_tasks(self):
        c=self.colors
        bar=ctk.CTkFrame(self.content,fg_color="transparent");bar.pack(fill="x",pady=(0,14))
        self.label(bar,"Tareas del equipo",17,"bold").pack(side="left")
        if self.role=="owner":self.btn(bar,"+  Nueva tarea",self.create_task,solid=True,width=130).pack(side="right")
        board=ctk.CTkFrame(self.content,fg_color="transparent");board.pack(fill="both",expand=True)
        tasks=self.store.tasks(self.user["_id"],self.workspace["_id"])
        for col,(status,title) in enumerate([("todo","Por hacer"),("doing","En curso"),("done","Terminado")]):
            lane=self.frame(board,fg=c["sidebar"]);lane.grid(row=0,column=col,sticky="nsew",padx=(0,12) if col<2 else 0)
            board.grid_columnconfigure(col,weight=1,uniform="lane");board.grid_rowconfigure(0,weight=1)
            self.label(lane,title+"   "+str(sum(t["status"]==status for t in tasks)),13,"bold").pack(anchor="w",padx=14,pady=16)
            inner=ctk.CTkScrollableFrame(lane,fg_color="transparent");inner.pack(fill="both",expand=True,padx=8,pady=(0,8))
            for t in [x for x in tasks if x["status"]==status]:
                card=self.frame(inner);card.pack(fill="x",pady=(0,9))
                self.label(card,t["priority"].upper()+"  /  "+t["assignee"],9,"bold",color=c["muted"]).pack(anchor="w",padx=13,pady=(13,7))
                self.label(card,t["title"],13,"bold",wraplength=245,justify="left").pack(anchor="w",padx=13)
                if t.get("description"):self.label(card,t["description"][:130],11,color=c["muted"],wraplength=245,justify="left").pack(anchor="w",padx=13,pady=(6,12))
                next_status={"todo":"doing","doing":"done","done":"todo"}[status]
                if self.role=="owner" or t.get("assignee_id")==self.user["_id"]:
                    self.btn(card,"Mover → "+{"todo":"Por hacer","doing":"En curso","done":"Terminado"}[next_status],lambda x=t,s=next_status:self.move_task(x,s),width=140,height=26).pack(anchor="w",padx=13,pady=(0,12))

    def render_files(self):
        c=self.colors
        bar=ctk.CTkFrame(self.content,fg_color="transparent");bar.pack(fill="x",pady=(0,14))
        self.label(bar,"Biblioteca de archivos",17,"bold").pack(side="left")
        self.btn(bar,"↑  Subir archivo",self.upload_file,solid=True,width=130).pack(side="right")
        listbox=ctk.CTkScrollableFrame(self.content,fg_color="transparent");listbox.pack(fill="both",expand=True)
        docs=self.store.attachments(self.user["_id"],self.workspace["_id"])
        if not docs:self.label(listbox,"Aún no hay archivos. Puedes subir imágenes y documentos de hasta 5 MB.",13,color=c["muted"]).pack(pady=70)
        for f in docs:
            row=self.frame(listbox);row.pack(fill="x",pady=(0,8))
            self.label(row,"▣",25).pack(side="left",padx=16,pady=15)
            names=ctk.CTkFrame(row,fg_color="transparent");names.pack(side="left",fill="x",expand=True)
            self.label(names,f["name"],13,"bold").pack(anchor="w")
            self.label(names,f["uploader"]+"  ·  "+short_date(f["created_at"])+"  ·  "+str(round(f["size"]/1024))+" KB",10,color=c["muted"]).pack(anchor="w",pady=(3,0))
            self.btn(row,"Descargar ↓",lambda x=f:self.download_file(x),width=110).pack(side="right",padx=16)

    def render_members(self):
        c=self.colors
        bar=ctk.CTkFrame(self.content,fg_color="transparent");bar.pack(fill="x",pady=(0,14))
        self.label(bar,"Personas del espacio",17,"bold").pack(side="left")
        if self.role=="owner":self.btn(bar,"+  Agregar persona",self.add_member,solid=True,width=150).pack(side="right")
        listbox=ctk.CTkScrollableFrame(self.content,fg_color="transparent");listbox.pack(fill="both",expand=True)
        for m in self.store.members(self.user["_id"],self.workspace["_id"]):
            row=self.frame(listbox);row.pack(fill="x",pady=(0,8))
            self.label(row,"◯",25).pack(side="left",padx=16,pady=14)
            names=ctk.CTkFrame(row,fg_color="transparent");names.pack(side="left",fill="x",expand=True)
            self.label(names,m["name"],13,"bold").pack(anchor="w")
            self.label(names,"@"+m["username"],10,color=c["muted"]).pack(anchor="w")
            self.label(row,m["role"].upper(),10,"bold",color=c["muted"]).pack(side="right",padx=20)

    def dialog(self,title,fields,submit,label="Guardar"):
        win=ctk.CTkToplevel(self);win.title(title);win.geometry("470x"+str(160+70*len(fields)));win.resizable(False,False)
        win.transient(self);win.grab_set();win.configure(fg_color=self.colors["bg"])
        self.label(win,title,22,"bold").pack(anchor="w",padx=24,pady=(23,17))
        values={}
        for key,caption,placeholder,secret in fields:
            self.label(win,caption,10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=24,pady=(6,4))
            entry=self.entry(win,placeholder,show="•" if secret else None)
            entry.configure(width=420);entry.pack(padx=24)
            values[key]=entry
        def finish():
            try:
                submit({k:v.get() for k,v in values.items()})
                win.destroy();self.render_app()
            except Exception as exc:messagebox.showerror(title,str(exc),parent=win)
        self.btn(win,label,finish,solid=True,width=420,height=40).pack(padx=24,pady=22)
        win.after(100,lambda:next(iter(values.values())).focus_set())

    def create_workspace(self):self.dialog("Nuevo espacio",[("name","NOMBRE","Nombre del espacio",False)],lambda v:self.store.create_workspace(self.user["_id"],v["name"]),"Crear espacio")
    def create_channel(self):self.dialog("Crear canal",[("name","NOMBRE","Ej. novedades",False),("description","DESCRIPCIÓN","¿Para qué usarán este canal?",False)],lambda v:self.store.create_channel(self.user["_id"],self.workspace["_id"],v["name"],v["description"]),"Crear canal")

    def add_member(self):
        def submit(v):
            self.store.invite_member(self.user["_id"],self.workspace["_id"],v["name"],v["username"],v["password"])
            messagebox.showinfo("Persona agregada","La persona ya puede iniciar sesión con el usuario y contraseña que elegiste.")
        self.dialog("Agregar persona",[("name","NOMBRE","Nombre completo",False),("username","USUARIO","Usuario para acceder",False),("password","CONTRASEÑA","Mínimo 8 caracteres",True)],submit,"Agregar persona")

    def compose_post(self):
        channels=self.store.channels(self.user["_id"],self.workspace["_id"])
        members=[m for m in self.store.members(self.user["_id"],self.workspace["_id"]) if m["_id"]!=self.user["_id"]]
        if not channels:messagebox.showwarning("Canales","Crea un canal primero");return
        win=ctk.CTkToplevel(self);win.title("Nueva actualización");win.geometry("600x700");win.transient(self);win.grab_set();win.configure(fg_color=self.colors["bg"])
        self.label(win,"Nueva actualización",24,"bold").pack(anchor="w",padx=24,pady=(23,18))
        self.label(win,"CANAL",10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=24)
        choice=ctk.CTkOptionMenu(win,values=[c["name"] for c in channels],width=550,fg_color=self.colors["surface2"],button_color=self.colors["hover"],text_color=self.colors["text"])
        choice.pack(padx=24,pady=(7,13));choice.set(self.channel["name"] if self.channel else channels[0]["name"])
        self.label(win,"TIPO",10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=24)
        kind=ctk.CTkOptionMenu(win,values=["Actualización","Anuncio","Hito","Pregunta"] if self.role=="owner" else ["Actualización","Pregunta"],width=550,fg_color=self.colors["surface2"],button_color=self.colors["hover"],text_color=self.colors["text"])
        kind.pack(padx=24,pady=(7,13))
        self.label(win,"DESTINATARIO",10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=24)
        target=ctk.CTkOptionMenu(win,values=["Todo el canal"]+["@"+m["username"] for m in members],width=550,fg_color=self.colors["surface2"],button_color=self.colors["hover"],text_color=self.colors["text"])
        target.pack(padx=24,pady=(7,13))
        title=self.entry(win,"Título de la publicación");title.configure(width=550);title.pack(padx=24,pady=(0,12))
        body=ctk.CTkTextbox(win,width=550,height=180,fg_color=self.colors["surface2"],border_width=1,border_color=self.colors["border"]);body.pack(padx=24)
        paths=[];files_label=self.label(win,"Sin archivos adjuntos · máximo 5 MB por archivo",11,color=self.colors["muted"]);files_label.pack(anchor="w",padx=24,pady=(12,6))
        def attach():
            paths.extend(filedialog.askopenfilenames(parent=win,title="Adjuntar archivos"))
            files_label.configure(text=str(len(paths))+" archivo(s) seleccionado(s)")
        self.btn(win,"⌁  Adjuntar fotos o archivos",attach,width=220).pack(anchor="w",padx=24)
        def publish():
            try:
                channel=next(c for c in channels if c["name"]==choice.get())
                type_key={"Actualización":"update","Anuncio":"announcement","Hito":"milestone","Pregunta":"question"}[kind.get()]
                recipient=next((m["_id"] for m in members if "@"+m["username"]==target.get()),None)
                self.store.create_post(self.user["_id"],self.workspace["_id"],channel["_id"],title.get(),body.get("1.0","end"),type_key,paths,recipient)
                win.destroy();self.render_content()
            except Exception as exc:messagebox.showerror("Publicar",str(exc),parent=win)
        self.btn(win,"Publicar actualización  →",publish,solid=True,width=550,height=42).pack(padx=24,pady=20)

    def open_post(self,post):
        win=ctk.CTkToplevel(self);win.title(post["title"]);win.geometry("620x710");win.transient(self);win.configure(fg_color=self.colors["bg"])
        inner=ctk.CTkScrollableFrame(win,fg_color="transparent");inner.pack(fill="both",expand=True,padx=10,pady=10)
        self.label(inner,"#"+post["channel"]+"  /  "+post["kind"].upper(),10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=15,pady=(15,10))
        self.label(inner,post["title"],25,"bold",wraplength=530,justify="left").pack(anchor="w",padx=15)
        self.label(inner,post["author"]+" · "+short_date(post["created_at"]),11,color=self.colors["muted"]).pack(anchor="w",padx=15,pady=(8,22))
        text=ctk.CTkTextbox(inner,width=535,height=185,fg_color=self.colors["surface"],border_width=1,border_color=self.colors["border"]);text.pack(padx=15);text.insert("1.0",post["body"]);text.configure(state="disabled")
        attachments=self.store.attachments(self.user["_id"],self.workspace["_id"])
        attached=[x for x in attachments if x["_id"] in post.get("attachments",[])]
        for f in attached:
            if f.get("mime","").startswith("image/"):
                try:
                    _, raw=self.store.read_attachment(self.user["_id"],self.workspace["_id"],f["_id"])
                    preview=Image.open(BytesIO(raw));preview.thumbnail((560,180))
                    image=ctk.CTkImage(light_image=preview,dark_image=preview,size=preview.size)
                    label=ctk.CTkLabel(inner,text="",image=image)
                    label.image=image
                    label.pack(anchor="w",padx=15,pady=(10,0))
                except Exception:pass
        for f in attached:self.btn(inner,"⌁  "+f["name"]+"   ↓",lambda x=f:self.download_file(x),width=535,anchor="w").pack(padx=15,pady=(9,0))
        self.btn(inner,"◌  Ver comentarios",lambda:self.open_comments(post),width=535).pack(padx=15,pady=(16,0))
        if post["author_id"]==self.user["_id"] or self.role=="owner":
            def delete():
                if messagebox.askyesno("Eliminar publicación","¿Eliminar esta actualización?",parent=win):
                    self.store.delete_post(self.user["_id"],self.workspace["_id"],post["_id"])
                    win.destroy();self.render_content()
            self.btn(inner,"Eliminar publicación",delete,width=535).pack(padx=15,pady=(9,0))

    def open_comments(self,post):
        win=ctk.CTkToplevel(self);win.title("Comentarios");win.geometry("510x520");win.transient(self);win.configure(fg_color=self.colors["bg"])
        self.label(win,"Comentarios",22,"bold").pack(anchor="w",padx=22,pady=(22,5))
        self.label(win,post["title"],11,color=self.colors["muted"]).pack(anchor="w",padx=22,pady=(0,15))
        scroll=ctk.CTkScrollableFrame(win,fg_color="transparent");scroll.pack(fill="both",expand=True,padx=20)
        def refresh():
            for child in scroll.winfo_children():child.destroy()
            for item in self.store.comments(self.user["_id"],self.workspace["_id"],post["_id"]):
                card=self.frame(scroll);card.pack(fill="x",pady=(0,8))
                self.label(card,item["author"]+"  ·  "+short_date(item["created_at"]),10,"bold",color=self.colors["muted"]).pack(anchor="w",padx=12,pady=(10,4))
                self.label(card,item["body"],12,wraplength=430,justify="left").pack(anchor="w",padx=12,pady=(0,12))
        refresh()
        entry=self.entry(win,"Escribe un comentario...");entry.configure(width=466);entry.pack(padx=20,pady=(12,6))
        def send():
            try:self.store.add_comment(self.user["_id"],self.workspace["_id"],post["_id"],entry.get());entry.delete(0,"end");refresh();self.render_content()
            except Exception as exc:messagebox.showerror("Comentar",str(exc),parent=win)
        self.btn(win,"Enviar comentario",send,solid=True,width=466).pack(padx=20,pady=(0,16))

    def react(self,post):
        try:self.store.toggle_reaction(self.user["_id"],self.workspace["_id"],post["_id"]);self.render_content()
        except Exception as exc:messagebox.showerror("Reacción",str(exc))

    def create_task(self):
        channels=self.store.channels(self.user["_id"],self.workspace["_id"])
        if not channels:messagebox.showwarning("Canales","Crea un canal primero");return
        members=self.store.members(self.user["_id"],self.workspace["_id"])
        def submit(v):
            channel=self.channel or channels[0]
            assignee=next((m["_id"] for m in members if m["username"].lower()==v["assignee"].strip().lower()),None) if v["assignee"].strip() else None
            if v["assignee"].strip() and not assignee:raise ValueError("Ese usuario no pertenece al espacio")
            self.store.create_task(self.user["_id"],self.workspace["_id"],channel["_id"],v["title"],v["description"],assignee,v["priority"].strip().lower() or "medium")
        self.dialog("Nueva tarea",[("title","TÍTULO","¿Qué hay que hacer?",False),("description","DESCRIPCIÓN","Detalles de la tarea",False),("assignee","ASIGNAR A","Usuario del equipo (opcional)",False),("priority","PRIORIDAD","low / medium / high",False)],submit,"Crear tarea")

    def move_task(self,task,status):
        try:self.store.set_task_status(self.user["_id"],self.workspace["_id"],task["_id"],status);self.render_content()
        except Exception as exc:messagebox.showerror("Tarea",str(exc))

    def upload_file(self):
        path=filedialog.askopenfilename(title="Subir archivo a Atlas")
        if not path:return
        try:self.store.add_attachment(self.user["_id"],self.workspace["_id"],path);self.render_content()
        except Exception as exc:messagebox.showerror("Archivo",str(exc))

    def download_file(self,file):
        path=filedialog.asksaveasfilename(initialfile=file["name"],title="Guardar archivo")
        if not path:return
        try:self.store.save_attachment(self.user["_id"],self.workspace["_id"],file["_id"],path);messagebox.showinfo("Descarga","Archivo guardado correctamente")
        except Exception as exc:messagebox.showerror("Descarga",str(exc))

    def show_notifications(self):
        items=self.store.notifications(self.user["_id"],self.workspace["_id"])
        win=ctk.CTkToplevel(self);win.title("Notificaciones");win.geometry("420x480");win.configure(fg_color=self.colors["bg"])
        self.label(win,"Notificaciones",22,"bold").pack(anchor="w",padx=20,pady=20)
        scroll=ctk.CTkScrollableFrame(win,fg_color="transparent");scroll.pack(fill="both",expand=True,padx=17)
        if not items:self.label(scroll,"Todo al día.",13,color=self.colors["muted"]).pack(pady=30)
        for item in items:
            card=self.frame(scroll);card.pack(fill="x",pady=(0,8))
            self.label(card,item["title"],12,"bold").pack(anchor="w",padx=12,pady=(10,3))
            self.label(card,item["body"],11,color=self.colors["muted"],wraplength=350).pack(anchor="w",padx=12,pady=(0,9))
        self.store.mark_read(self.user["_id"],self.workspace["_id"])


if __name__=="__main__":
    app=Nexo();app.mainloop()
