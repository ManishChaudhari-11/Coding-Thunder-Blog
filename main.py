import json
import math
import os
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from regex import F
from werkzeug.utils import secure_filename

with open("config.json", "r") as c:
    params = json.load(c)["params"]

local_server = params["local_server"]
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = params["upload_location"]
app.secret_key = "super-secret-key"
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT="465",
    MAIL_USE_SSL=True,
    MAIL_USERNAME=params["gmail-user"],
    MAIL_PASSWORD=params["gmail-password"],
)
mail = Mail(app)

if local_server:
    app.config["SQLALCHEMY_DATABASE_URI"] = params["local_uri"]
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = params["prod_uri"]

db = SQLAlchemy(app)


class Contacts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone_num = db.Column(db.String(12), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    date = db.Column(db.String(12), nullable=True)


class Posts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    tagline = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(50), nullable=False)
    content = db.Column(db.String(3000), nullable=False)
    date = db.Column(db.String(12), nullable=True)
    img_file = db.Column(db.String(50), nullable=True)


@app.route("/")
def home():
    # posts = Posts.query.filter_by().all()
    # last = math.floor(int(len(posts) / int(params["no_of_posts"]))) + 1
    # print(last)
    page = request.args.get("page")
    if not str(page).isnumeric():
        page = 0

    page = int(page)
    # posts = posts[
    #     (page - 1)
    #     * int(params["no_of_posts"]) : (page - 1)
    #     * int(params["no_of_posts"])
    #     + int(params["no_of_posts"])
    # ]
    # if page == 1:
    #     prev = "#"
    #     nextp = "/?page=" + str(page + 1)
    # elif page == last:
    #     prev = "/?page=" + str(page - 1)
    #     nextp = "#"
    # else:
    #     prev = "/?page=" + str(page - 1)
    #     nextp = "/?page=" + str(page + 1)

    posts = Posts.query.paginate(
        per_page=int(params["no_of_posts"]), page=page, error_out=False
    )
    if posts.has_next:
        next_url = url_for("home", page=posts.next_num)
    else:
        next_url = None

    if posts.has_prev:
        prev_url = url_for("home", page=posts.prev_num)
    else:
        prev_url = None
    return render_template(
        "index.html", params=params, posts=posts, prev=prev_url, next=next_url
    )


@app.route("/about")
def about():
    return render_template("about.html", params=params)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # Add entry to the database
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        message = request.form.get("message")

        entry = Contacts(
            name=name,
            email=email,
            phone_num=phone,
            message=message,
            date=datetime.now(),
        )
        db.session.add(entry)
        db.session.commit()
        mail.send_message(
            f"New message from {name}",
            sender=email,
            recipients=[params["gmail-user"]],
            body=message + "\nContact :\nPhone - " + phone + "\nEmail - " + email,
        )

    return render_template("contact.html", params=params)


@app.route("/post/<string:post_slug>", methods=["GET"])
def get_post(post_slug):
    post = Posts.query.filter_by(slug=post_slug).first()
    paragraphs = post.content.split("\\")
    for paragraph in paragraphs:
        paragraph = paragraph.replace("\\", "")
    return render_template("post.html", params=params, post=post, paragraphs=paragraphs)


@app.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if request.method != "POST":
        return render_template("signin.html", params=params)
    username = request.form.get("uname")
    userpass = request.form.get("pass")

    if username == params["admin_user"] and userpass == params["admin_password"]:
        session["user"] = username
        return redirect("/dashboard")


@app.route("/sign-out")
def logout():
    session.pop("user", None)
    return redirect("/sign-in")


@app.route("/dashboard", methods=["GET"])
def dashboard():
    if "user" not in session or session["user"] != params["admin_user"]:
        return redirect("/sign-in")
    posts = Posts.query.all()
    return render_template("dashboard.html", params=params, posts=posts)


@app.route("/add-edit/<string:sno>", methods=["GET", "POST"])
def add_edit(sno):
    if "user" not in session or session["user"] != params["admin_user"]:
        return redirect("/sign-in")

    post = Posts.query.filter_by(sno=sno).first()
    if request.method != "POST":
        return render_template("add-edit.html", params=params, post=post, sno=sno)

    title = request.form.get("title")
    tagline = request.form.get("tagline")
    slug = request.form.get("slug")
    content = request.form.get("content")
    image_file = request.files.get("img_file")

    if image_file and allowed_file(image_file.filename):
        img_filename = post.img_file
        if sno == "0" or image_file.filename:
            img_filename = secure_filename(slug + ".jpg")
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], img_filename))

    if sno == "0":
        post = Posts(
            title=title,
            tagline=tagline,
            slug=slug,
            content=content,
            img_file=image_file.filename,
            date=datetime.now(),
        )
        db.session.add(post)
    else:
        post.title = title
        post.tagline = tagline
        post.slug = slug
        post.content = content
        if image_file and allowed_file(image_file.filename):
            post.img_file = img_filename

    db.session.commit()
    return redirect("/dashboard")


@app.route("/delete/<string:sno>", methods=["GET", "POST"])
def delete(sno):
    if "user" not in session or session["user"] != params["admin_user"]:
        return redirect("/sign-in")
    post = Posts.query.filter_by(sno=sno).first()
    db.session.delete(post)
    db.session.commit()
    return redirect("/dashboard")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "png",
        "jpg",
        "jpeg",
    }


app.run(debug=True)
