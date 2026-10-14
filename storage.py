import json
import os
import uuid
from datetime import datetime
from decimal import Decimal, DecimalException


DEFAULT_SETTINGS = {'schemaVersion': 1, 'theme': 'dark', 'decimalPlaces': 6, 'saveHistory': True}


class Store:
    def __init__(self, directory):
        self.directory = directory
        self.error = ''
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            self.error = 'Local storage is unavailable. Changes may not be saved.'
        self.settings = dict(DEFAULT_SETTINGS)
        raw = self.read('settings.json', {})
        if isinstance(raw, dict):
            if raw.get('theme') in ('light', 'dark'):
                self.settings['theme'] = raw['theme']
            places = raw.get('decimalPlaces')
            if type(places) is int and 0 <= places <= 10:
                self.settings['decimalPlaces'] = places
            if type(raw.get('saveHistory')) is bool:
                self.settings['saveHistory'] = raw['saveHistory']
        self.history = []
        raw_history = self.read('history.json', [])
        seen = set()
        if isinstance(raw_history, list):
            for item in raw_history:
                if not isinstance(item, dict):
                    continue
                try:
                    ident = item['id']
                    expression = item['expression']
                    result = item['result']
                    created = item['createdAt']
                    if not all(isinstance(v, str) for v in (ident, expression, result, created)):
                        continue
                    if not ident or len(ident) > 100 or ident in seen or not expression or len(expression) > 512 or not result or len(result) > 4096:
                        continue
                    if not Decimal(result).is_finite():
                        continue
                    datetime.fromisoformat(created)
                    self.history.append({'id': ident, 'expression': expression, 'result': result, 'createdAt': created})
                    seen.add(ident)
                except (KeyError, ValueError, TypeError, DecimalException, OverflowError):
                    continue
        self.history = self.history[-1000:]
        self.write('settings.json', self.settings)
        self.write('history.json', self.history)

    def read(self, name, default):
        try:
            with open(os.path.join(self.directory, name), 'r', encoding='utf-8') as handle:
                return json.load(handle)
        except (OSError, ValueError, TypeError, UnicodeError):
            return default

    def write(self, name, data):
        path = os.path.join(self.directory, name)
        temporary = path + '.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=True, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            return True
        except (OSError, ValueError, TypeError):
            self.error = 'Could not save changes on this device.'
            try:
                os.remove(temporary)
            except OSError:
                pass
            return False

    def preference(self, key, value):
        self.settings[key] = value
        return self.write('settings.json', self.settings)

    def add(self, expression, result):
        self.history.append({'id': uuid.uuid4().hex, 'expression': expression, 'result': result,
                             'createdAt': datetime.now().astimezone().isoformat(timespec='seconds')})
        self.history = self.history[-1000:]
        return self.write('history.json', self.history)

    def delete(self, ident):
        self.history = [entry for entry in self.history if entry['id'] != ident]
        return self.write('history.json', self.history)

    def clear(self):
        self.history = []
        return self.write('history.json', self.history)
