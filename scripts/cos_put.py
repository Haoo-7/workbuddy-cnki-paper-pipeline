"""腾讯云 COS 临时密钥签名上传（ima create_media 返回的凭据专用）。

ima 的 create_media 会给出一组临时密钥 + 目标 cos_key，但没有直传接口，
必须自己按 q-sign-algorithm=sha1 算签名做 PUT。

用法（命令行）：
    python cos_put.py media.json --file /path/to.pdf [--content-type application/pdf]

media.json 可以是 create_media 的原始返回（含 cos_credential），
也可以只是 cos_credential 对象本身。

作为模块：
    from cos_put import upload
    upload(cos_credential_dict, "/path/to.pdf")
"""

import argparse
import hashlib
import hmac
import json
import sys
import urllib.parse
import urllib.request


def sign(secret_id, secret_key, start, end, host, path):
    sign_time = "%s;%s" % (start, end)
    sign_key = hmac.new(secret_key.encode(), sign_time.encode(), hashlib.sha1).hexdigest()
    header_string = "host=" + urllib.parse.quote(host, safe="")
    http_string = "put\n%s\n\n%s\n" % (urllib.parse.quote(path, safe="/"), header_string)
    string_to_sign = "sha1\n%s\n%s\n" % (sign_time, hashlib.sha1(http_string.encode()).hexdigest())
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    return ("q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s"
            "&q-header-list=host&q-url-param-list=&q-signature=%s"
            % (secret_id, sign_time, sign_time, signature))


def upload(cred, file_path, content_type="application/pdf", timeout=300):
    """cred 为 create_media 返回的 cos_credential 对象。返回 HTTP 状态码。"""
    bucket, region, key = cred["bucket_name"], cred["region"], cred["cos_key"]
    host = "%s.cos.%s.myqcloud.com" % (bucket, region)
    path = "/" + key
    auth = sign(cred["secret_id"], cred["secret_key"], cred["start_time"], cred["expired_time"],
                host, path)
    url = "https://%s%s" % (host, urllib.parse.quote(path))
    data = open(file_path, "rb").read()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", auth)
    req.add_header("x-cos-security-token", cred["token"])
    req.add_header("Content-Type", content_type)
    req.add_header("Host", host)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def _extract(obj):
    if isinstance(obj, dict) and "cos_credential" in obj:
        return obj["cos_credential"]
    return obj


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="create_media 返回（或其中 cos_credential）保存成的 JSON")
    ap.add_argument("--file", required=True)
    ap.add_argument("--content-type", default="application/pdf")
    a = ap.parse_args()
    cred = _extract(json.load(open(a.media, encoding="utf-8")))
    print(upload(cred, a.file, a.content_type))
