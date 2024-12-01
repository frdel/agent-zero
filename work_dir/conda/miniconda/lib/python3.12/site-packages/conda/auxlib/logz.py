from itertools import islice
from json import JSONEncoder, dumps, loads
from logging import getLogger, INFO, Formatter, StreamHandler, DEBUG
from sys import stderr

from . import NullHandler

log = getLogger(__name__)
root_log = getLogger()

NullHandler = NullHandler

DEBUG_FORMATTER = Formatter(
    "[%(levelname)s] [%(asctime)s.%(msecs)03d] %(process)d %(name)s:%(funcName)s(%(lineno)d):\n"
    "%(message)s\n",
    "%Y-%m-%d %H:%M:%S")

INFO_FORMATTER = Formatter(
    "[%(levelname)s] [%(asctime)s.%(msecs)03d] %(process)d %(name)s(%(lineno)d): %(message)s\n",
    "%Y-%m-%d %H:%M:%S")


def set_root_level(level=INFO):
    root_log.setLevel(level)


def attach_stderr(level=INFO):
    has_stderr_handler = any(handler.name == 'stderr' for handler in root_log.handlers)
    if not has_stderr_handler:
        handler = StreamHandler(stderr)
        handler.name = 'stderr'
        if level is not None:
            handler.setLevel(level)
        handler.setFormatter(DEBUG_FORMATTER if level == DEBUG else INFO_FORMATTER)
        root_log.addHandler(handler)
        return True
    else:
        return False


def detach_stderr():
    for handler in root_log.handlers:
        if handler.name == 'stderr':
            root_log.removeHandler(handler)
            return True
    return False


def initialize_logging(level=INFO):
    attach_stderr(level)


class DumpEncoder(JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'dump'):
            return obj.dump()
        # Let the base class default method raise the TypeError
        return super().default(obj)


_DUMPS = DumpEncoder(indent=2, ensure_ascii=False, sort_keys=True).encode


def jsondumps(obj):
    return _DUMPS(obj)


def fullname(obj):
    try:
        return obj.__module__ + "." + obj.__class__.__name__
    except AttributeError:
        return obj.__class__.__name__


request_header_sort_dict = {
    'Host': '\x00\x00',
    'User-Agent': '\x00\x01',
}
def request_header_sort_key(item):
    return request_header_sort_dict.get(item[0], item[0].lower())


response_header_sort_dict = {
    'Content-Length': '\x7e\x7e\x61',
    'Connection': '\x7e\x7e\x62',
}
def response_header_sort_key(item):
    return response_header_sort_dict.get(item[0], item[0].lower())


def stringify(obj, content_max_len=0):
    def bottle_builder(builder, bottle_object):
        builder.append(
            "{} {}{} {}".format(
                bottle_object.method,
                bottle_object.path,
                bottle_object.environ.get("QUERY_STRING", ""),
                bottle_object.get("SERVER_PROTOCOL"),
            )
        )
        builder += [f"{key}: {value}" for key, value in bottle_object.headers.items()]
        builder.append('')
        body = bottle_object.body.read().strip()
        if body:
            builder.append(body)

    def requests_models_PreparedRequest_builder(builder, request_object):
        builder.append(
            ">>{} {} {}".format(
                request_object.method,
                request_object.path_url,
                request_object.url.split(":", 1)[0].upper(),
            )
        )
        builder.extend(
            f"> {key}: {value}"
            for key, value in sorted(request_object.headers.items(), key=request_header_sort_key)
        )
        builder.append("")
        if request_object.body:
            builder.append(request_object.body)

    def requests_models_Response_builder(builder, response_object):
        builder.append(
            "<<{} {} {}".format(
                response_object.url.split(":", 1)[0].upper(),
                response_object.status_code,
                response_object.reason,
            )
        )
        builder.extend(
            f"< {key}: {value}"
            for key, value in sorted(response_object.headers.items(), key=response_header_sort_key)
        )
        elapsed = str(response_object.elapsed).split(":", 1)[-1]
        builder.append(f"< Elapsed: {elapsed}")
        if content_max_len:
            builder.append('')
            content_type = response_object.headers.get('Content-Type')
            if content_type == 'application/json':
                text = response_object.text
                if len(text) > content_max_len:
                    content = text
                else:
                    resp = loads(text)
                    resp = dict(islice(resp.items(), content_max_len))
                    content = dumps(resp, indent=2)
                content = content[:content_max_len] if len(content) > content_max_len else content
                builder.append(content)
                builder.append('')
            elif content_type is not None and (content_type.startswith('text/')
                                               or content_type == 'application/xml'):
                text = response_object.text
                content = text[:content_max_len] if len(text) > content_max_len else text
                builder.append(content)

    try:
        name = fullname(obj)
        builder = ['']  # start with new line
        if name.startswith('bottle.'):
            bottle_builder(builder, obj)
        elif name.endswith('requests.models.PreparedRequest'):
            requests_models_PreparedRequest_builder(builder, obj)
        elif name.endswith('requests.models.Response'):
            if getattr(obj, 'request'):
                requests_models_PreparedRequest_builder(builder, obj.request)
            else:
                log.info("request is 'None' for Response object with url %s", obj.url)
            requests_models_Response_builder(builder, obj)
        else:
            return None
        builder.append('')  # end with new line
        return "\n".join(builder)
    except Exception as e:
        log.exception(e)
