import logging

class AppLogger:
    _loggers = {}

    @staticmethod
    def get_logger(name="app"):
        if name in AppLogger._loggers:
            return AppLogger._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # Console formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        logger.propagate = False
        AppLogger._loggers[name] = logger
        return logger
