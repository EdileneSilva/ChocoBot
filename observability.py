import contextvars, json, logging, sys, time

request_id = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id.get(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


log = logging.getLogger("chocobot")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
log.handlers = [_handler]
log.setLevel(logging.INFO)
log.propagate = False


def log_event(level, event, exc_info=False, **fields):
    """Écrit un événement JSON. Ne jamais passer de contenu de message ni d'allergie."""
    log.log(getattr(logging, level.upper()), event, exc_info=exc_info, extra={"fields": fields})
