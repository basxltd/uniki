import base64
import datetime
import io
import random
import sqlite3
import uuid as pyuuid

import flask
import qrcode

MAX_AGE_DAYS = 30


application = app = flask.Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    c = cursor()
    c.execute("SELECT uuid, MAX(used) FROM keys GROUP BY uuid ORDER BY MAX(used) DESC")
    return flask.render_template(
        "home.html",
        keys=c.fetchall(),
        nicedate=nicedate,
        nicetime=nicetime,
        uuid2pic=uuid2pic,
        date=datetime.date.today(),
    )


@app.route("/genkey", methods=["POST"])
def genkey():
    uuid = pyuuid.uuid1()
    c = cursor()
    c.execute(
        "INSERT INTO keys VALUES (?, ?)",
        (uuid.hex, None),
    )
    c.connection.commit()
    return flask.redirect(f"/showkey/{uuid.hex}")


@app.route("/showkey/<uuid>", methods=["GET"])
def showkey(uuid):
    c = cursor()
    c.execute("SELECT * FROM keys WHERE uuid = ? ORDER BY used DESC", (uuid,))
    uses = c.fetchall()

    if uses:
        return flask.render_template(
            "showkey.html",
            uses=uses,
            to_qrcode=to_qrcode,
            nicedate=nicedate,
            nicetime=nicetime,
            uuid2pic=uuid2pic,
            used_already=used_already(uuid, use_once),
            too_old=too_old(uuid),
        )
    return flask.redirect("/")


@app.route("/usekey/<uuid>", methods=["POST"])
def usekey(uuid):
    c = cursor()
    c.execute("SELECT * FROM keys WHERE uuid = ? ORDER BY used DESC", (uuid,))
    result = c.fetchone()
    if result and not used_already(uuid, use_once) and not too_old(uuid):
        c.execute(
            "INSERT INTO keys VALUES (?, ?)",
            (uuid, datetime.datetime.now().isoformat()),
        )
        c.connection.commit()
        return flask.redirect(f"/showkey/{uuid}")
    return flask.redirect("/")


# CHECK FUNCTIONS
def use_once_per_day(uses):
    return (
        any(u["used"] for u in uses if u["used"])
        and datetime.datetime.fromisoformat(
            max(u["used"] for u in uses if u["used"])
        ).date()
        >= datetime.date.today()
    )


def use_once(uses):
    return any(u["used"] for u in uses if u["used"])


# HELPERS ----------------------------------------------


def used_already(uuid, check_func):
    c = cursor()
    c.execute("SELECT * FROM keys WHERE uuid = ? ORDER BY used DESC", (uuid,))
    uses = c.fetchall()
    return check_func(uses)


def too_old(uuid):
    c = cursor()
    c.execute("SELECT * FROM keys WHERE uuid = ? ORDER BY used DESC", (uuid,))
    uses = c.fetchall()

    return (
        any(u["used"] for u in uses if u["used"])
        and (
            datetime.datetime.now()
            - datetime.datetime.fromisoformat(min(u["used"] for u in uses if u["used"]))
        ).days
        > MAX_AGE_DAYS
    )


def to_qrcode(data, download):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data)
    qr.make()
    img_data = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(img_data)
    b64data = base64.b64encode(img_data.getvalue()).decode()
    if download:
        return (
            f'<a href="data:image/png;base64,{b64data}" '
            'download="key.png"><button>Get QR-Code</button></a>'
        )

    return (
        f'<img src="data:image/png;base64,{b64data}" '
        f"onclick=\"printimg('{b64data}');\"/>"
    )


def uuid2pic(uuid, size=32):
    random.seed(pyuuid.UUID(hex=uuid).int)
    dark = random.randint(0, 1) == 1
    background = "#eee" if dark else "#222"
    foreground = f"hsl({random.randint(0, 359)}, 100%, {'30%' if dark else '70%'})"
    ret = [
        f'<svg width={size} height={size} viewBox="0 0 8 8">',
        f'<rect width=16 height=16 style="fill: {background}" />',
    ]
    grid = []
    for i in range(8):
        for j in range(8):
            grid.append(random.randint(0, 1) == 1)
    mirror_x = random.randint(0, 1) == 1
    mirror_y = random.randint(0, 1) == 1
    if not mirror_x and not mirror_y:
        mirror_x, mirror_y = True, True

    for i in range(8):
        for j in range(8):
            x, y = j, i
            if mirror_x:
                x = 7 - j if j >= 4 else j
            if mirror_y:
                y = 7 - i if i >= 4 else i
            if grid[y * 8 + x]:
                ret.append(
                    f'<rect x={j} y={i} width=1 height=1 style="fill: {foreground}" />'
                )
    return "".join(ret + ["</svg>"])


def nicedate(date):
    if date:
        return datetime.datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
    return ""


def nicetime(date):
    if date:
        return datetime.datetime.fromisoformat(date).strftime("%H:%M")
    return ""


def cursor():
    if not hasattr(flask.g, "db"):
        flask.g.db = sqlite3.connect("db.sqlite")
        flask.g.db.row_factory = sqlite3.Row
    return flask.g.db.cursor()
