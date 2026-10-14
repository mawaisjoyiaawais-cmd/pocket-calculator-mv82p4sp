from datetime import datetime
from decimal import Decimal, DecimalException, localcontext

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import DictProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from engine import calculate, display_number, decimal_string, pretty, NUMBER_AT_END, CalculationError, IncompleteExpression
from storage import Store


DARK = {
    'bg': [0.043, 0.067, 0.11, 1], 'surface': [0.075, 0.11, 0.17, 1],
    'key': [0.12, 0.16, 0.23, 1], 'fg': [0.94, 0.96, 1, 1],
    'muted': [0.64, 0.71, 0.8, 1], 'accent': [0.22, 0.85, 0.73, 1],
    'onaccent': [0.025, 0.13, 0.12, 1], 'op': [0.105, 0.24, 0.26, 1],
    'danger': [1, 0.48, 0.51, 1]
}
LIGHT = {
    'bg': [0.94, 0.96, 0.98, 1], 'surface': [1, 1, 1, 1],
    'key': [0.86, 0.9, 0.94, 1], 'fg': [0.07, 0.12, 0.19, 1],
    'muted': [0.32, 0.4, 0.49, 1], 'accent': [0.04, 0.47, 0.4, 1],
    'onaccent': [1, 1, 1, 1], 'op': [0.78, 0.91, 0.88, 1],
    'danger': [0.73, 0.13, 0.2, 1]
}


class ToneBox(BoxLayout):
    tone = StringProperty('surface')


class Text(Label):
    tone = StringProperty('fg')


class RoundedButton(Button):
    role = StringProperty('normal')


class Toast(Text):
    pass


Builder.load_string('''
<ToneBox>:
    canvas.before:
        Color:
            rgba: app.palette[self.tone]
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(20)]
<Text>:
    color: app.palette[self.tone]
    font_size: sp(16)
<RoundedButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: app.palette['onaccent'] if self.role == 'primary' else (app.palette['danger'] if self.role == 'danger' else (app.palette['accent'] if self.role == 'operator' else app.palette['fg']))
    disabled_color: app.palette['muted']
    font_size: sp(16)
    halign: 'center'
    valign: 'middle'
    text_size: self.width - dp(12), self.height - dp(6)
    canvas.before:
        Color:
            rgba: app.palette['accent'] if self.role == 'primary' else (app.palette['op'] if self.role == 'operator' else app.palette['key'])
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
        Color:
            rgba: (1, 1, 1, .12) if self.state == 'down' else (0, 0, 0, 0)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
<Toast>:
    color: app.palette['onaccent']
    text_size: self.width - dp(24), self.height
    halign: 'center'
    valign: 'middle'
    font_size: sp(14)
    canvas.before:
        Color:
            rgba: app.palette['accent']
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
<Screen>:
    canvas.before:
        Color:
            rgba: app.palette['bg']
        Rectangle:
            pos: self.pos
            size: self.size
''')


def app():
    return App.get_running_app()


def button(text, callback, role='normal', **kwargs):
    widget = RoundedButton(text=text, role=role, **kwargs)
    widget.bind(on_release=lambda *_: callback())
    return widget


def wrapped(text, tone='fg', font=16, minimum=0):
    widget = Text(text=text, tone=tone, font_size=sp(font), size_hint_y=None,
                  halign='left', valign='middle')
    widget.bind(width=lambda obj, value: setattr(obj, 'text_size', (max(dp(20), value), None)))
    widget.bind(texture_size=lambda obj, size: setattr(obj, 'height', max(dp(minimum), size[1] + dp(12))))
    widget.height = dp(max(minimum, 40))
    return widget


def header(title, back=True):
    row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(10))
    if back:
        row.add_widget(button('Back', lambda: app().back(), size_hint_x=None, width=dp(68)))
    label = Text(text=title, font_size=sp(22), bold=True, halign='left', valign='middle')
    label.bind(size=lambda obj, val: setattr(obj, 'text_size', val))
    row.add_widget(label)
    return row


def scroll_list():
    scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
    grid = GridLayout(cols=1, spacing=dp(12), padding=[0, dp(4), 0, dp(16)], size_hint_y=None)
    grid.bind(minimum_height=grid.setter('height'))
    scroll.add_widget(grid)
    return scroll, grid


class CalculatorIcon(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw)
        app().bind(palette=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        size = min(self.width, self.height)
        x, y = self.center_x - size / 2, self.center_y - size / 2
        with self.canvas:
            Color(*app().palette['op'])
            RoundedRectangle(pos=(x, y), size=(size, size), radius=[size * .22])
            Color(*app().palette['accent'])
            RoundedRectangle(pos=(x + size * .2, y + size * .66), size=(size * .6, size * .14), radius=[size * .035])
            for row in range(2):
                for col in range(3):
                    RoundedRectangle(pos=(x + size * (.2 + col * .22), y + size * (.21 + row * .22)),
                                     size=(size * .15, size * .15), radius=[size * .035])


class LaunchScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', spacing=dp(14), padding=dp(30))
        layout.add_widget(Widget())
        layout.add_widget(CalculatorIcon(size_hint=(None, None), size=(dp(110), dp(110)), pos_hint={'center_x': .5}))
        layout.add_widget(Text(text='Pocket Calculator', bold=True, font_size=sp(27), size_hint_y=None, height=dp(52)))
        layout.add_widget(Text(text='Simple numbers. Clear answers.', tone='muted', size_hint_y=None, height=dp(32)))
        self.loading = Text(text='Preparing your workspace…', tone='muted', font_size=sp(14), size_hint_y=None, height=dp(48))
        layout.add_widget(self.loading)
        layout.add_widget(Widget())
        self.add_widget(layout)

    def on_enter(self, *_):
        Clock.schedule_once(lambda dt: app().initialize(), .35)


class HoldResult(Text):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pending = None
        self.touch_id = None
        self.origin = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.touch_id = touch.uid
            self.origin = touch.pos
            if self.pending:
                self.pending.cancel()
            self.pending = Clock.schedule_once(self.copy_result, .65)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.uid == self.touch_id and self.origin:
            if abs(touch.x - self.origin[0]) + abs(touch.y - self.origin[1]) > dp(12):
                self.cancel_hold()
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.uid == self.touch_id:
            self.cancel_hold()
        return super().on_touch_up(touch)

    def cancel_hold(self):
        if self.pending:
            self.pending.cancel()
        self.pending = None
        self.touch_id = None

    def copy_result(self, _):
        self.pending = None
        screen = app().manager.get_screen('calculator')
        if screen.preview_value is not None:
            app().copy(screen.preview_value)


class NumberLine(ScrollView):
    def __init__(self, result=False, **kwargs):
        super().__init__(do_scroll_y=False, do_scroll_x=True, bar_width=dp(2), **kwargs)
        cls = HoldResult if result else Text
        self.label = cls(size_hint=(None, 1), font_size=sp(40 if result else 20),
                         tone='fg' if result else 'muted', halign='right', valign='middle')
        self.add_widget(self.label)
        self.bind(width=self.resize)
        self.label.bind(texture_size=self.resize)

    def resize(self, *_):
        self.label.width = max(self.width, self.label.texture_size[0] + dp(16))

    def set_text(self, value):
        self.label.text = value
        Clock.schedule_once(lambda dt: setattr(self, 'scroll_x', 1), 0)


class CalculatorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expression = ''
        self.preview_value = '0'
        self.completed = False
        outer = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        title = header('Pocket Calculator', back=False)
        outer.add_widget(title)
        toolbar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        toolbar.add_widget(button('History', lambda: app().go('history')))
        toolbar.add_widget(button('Settings', lambda: app().go('settings')))
        outer.add_widget(toolbar)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        body = BoxLayout(orientation='vertical', spacing=dp(12), size_hint_y=None)
        scroll.bind(height=lambda obj, val: setattr(body, 'height', max(val, dp(470))))
        body.height = dp(470)
        display = ToneBox(orientation='vertical', padding=dp(16), spacing=dp(2), size_hint_y=None, height=dp(170))
        self.expression_line = NumberLine(size_hint_y=None, height=dp(42))
        self.result_line = NumberLine(result=True, size_hint_y=None, height=dp(66))
        self.hint = Text(text='Hold the result to copy', tone='muted', font_size=sp(12), halign='right', valign='middle')
        self.hint.bind(size=lambda obj, val: setattr(obj, 'text_size', val))
        display.add_widget(self.expression_line)
        display.add_widget(self.result_line)
        display.add_widget(self.hint)
        body.add_widget(display)
        keypad = GridLayout(cols=4, rows=5, spacing=dp(8))
        keys = [('AC', 'clear'), ('DEL', 'delete'), ('%', 'percent'), ('÷', '/'),
                ('7', '7'), ('8', '8'), ('9', '9'), ('×', '*'),
                ('4', '4'), ('5', '5'), ('6', '6'), ('−', '-'),
                ('1', '1'), ('2', '2'), ('3', '3'), ('+', '+'),
                ('±', 'sign'), ('0', '0'), ('.', '.'), ('=', '=')]
        for caption, key in keys:
            role = 'primary' if key == '=' else ('operator' if key in ('/', '*', '-', '+', 'percent', 'sign') else ('danger' if key == 'clear' else 'normal'))
            keypad.add_widget(button(caption, lambda value=key: self.press(value), role=role, font_size=sp(25 if key not in ('clear', 'delete') else 17)))
        body.add_widget(keypad)
        scroll.add_widget(body)
        outer.add_widget(scroll)
        self.add_widget(outer)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        self.expression_line.set_text(pretty(self.expression) or '0')
        try:
            self.preview_value = calculate(self.expression) if self.expression else '0'
            places = app().store.settings['decimalPlaces'] if app().store else 6
            self.result_line.set_text(display_number(self.preview_value, places))
            self.hint.tone = 'muted'
            self.hint.text = 'Result  •  Hold to copy full precision' if self.completed else 'Preview  •  Hold to copy full precision'
        except IncompleteExpression as error:
            self.preview_value = None
            self.result_line.set_text('—')
            self.hint.tone = 'muted'
            self.hint.text = str(error)
        except CalculationError as error:
            self.preview_value = None
            self.result_line.set_text('—')
            self.hint.tone = 'danger'
            self.hint.text = str(error)

    def load(self, expression):
        self.expression = expression
        self.completed = False
        self.refresh()

    def assign(self, expression):
        if len(expression) > 512:
            app().notify('Expression limit: 512 characters')
            return False
        self.expression = expression
        return True

    def press(self, key):
        if key == 'clear':
            self.expression = ''
            self.completed = False
        elif key == 'delete':
            self.expression = self.expression[:-1]
            self.completed = False
        elif key == '=':
            self.finish()
            return
        elif key in '+-*/':
            if self.completed and self.preview_value is not None:
                if not self.assign(self.preview_value):
                    return
            self.completed = False
            value = self.expression
            if not value:
                if key == '-':
                    self.expression = '-'
            elif value[-1] in '+-*/':
                if key == '-' and value[-1] != '-':
                    self.assign(value + '-')
                else:
                    base = value.rstrip('+-*/')
                    self.assign(base + key if base else ('-' if key == '-' else ''))
            else:
                self.assign(value + key)
        elif key in ('sign', 'percent'):
            if self.completed and self.preview_value is not None:
                if not self.assign(self.preview_value):
                    return
            self.completed = False
            match = NUMBER_AT_END.search(self.expression)
            if not match:
                if key == 'sign':
                    self.assign(self.expression[:-1] if self.expression.endswith('-') else self.expression + '-')
                else:
                    app().notify('Enter a number first')
            elif key == 'sign':
                start = match.start()
                unary = start > 0 and self.expression[start - 1] == '-' and (start == 1 or self.expression[start - 2] in '+-*/(')
                if unary:
                    self.assign(self.expression[:start - 1] + self.expression[start:])
                else:
                    self.assign(self.expression[:start] + '-' + self.expression[start:])
            else:
                try:
                    with localcontext() as ctx:
                        ctx.prec = max(80, len(match.group()) + 8)
                        value = decimal_string(Decimal(match.group()) / Decimal(100))
                    self.assign(self.expression[:match.start()] + value)
                except DecimalException:
                    app().notify('Cannot apply percent to this number')
        else:
            if self.completed:
                self.expression = ''
                self.completed = False
            if key == '.':
                match = NUMBER_AT_END.search(self.expression)
                if match and '.' in match.group():
                    return
                self.assign(self.expression + ('.' if match else '0.'))
            elif key.isdigit():
                self.assign(self.expression + key)
        self.refresh()

    def finish(self):
        if not self.expression:
            return
        self.refresh()
        if self.preview_value is None or self.completed:
            return
        self.completed = True
        if app().store.settings['saveHistory']:
            app().check_save(app().store.add(self.expression, self.preview_value))
        self.refresh()


class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        outer = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        outer.add_widget(header('History'))
        self.summary = wrapped('Your recent calculations', tone='muted', font=14)
        outer.add_widget(self.summary)
        self.clear_button = button('Clear History', lambda: app().confirm_clear(), role='danger', size_hint_y=None, height=dp(48))
        outer.add_widget(self.clear_button)
        self.scroll, self.list = scroll_list()
        outer.add_widget(self.scroll)
        self.add_widget(outer)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        self.list.clear_widgets()
        entries = app().store.history if app().store else []
        self.summary.text = '{} saved calculation{}'.format(len(entries), '' if len(entries) == 1 else 's')
        self.clear_button.disabled = not entries
        if not entries:
            self.list.add_widget(wrapped('No calculations yet', font=24, minimum=100))
            self.list.add_widget(wrapped('Complete a calculation with = and it will appear here when Save History is on.', tone='muted'))
            self.list.add_widget(button('Open Calculator', lambda: app().open_calculator(), role='primary', size_hint_y=None, height=dp(52)))
            return
        groups = {}
        for entry in reversed(entries):
            day = datetime.fromisoformat(entry['createdAt']).strftime('%A, %d %b %Y')
            groups.setdefault(day, []).append(entry)
        places = app().store.settings['decimalPlaces']
        for day, items in groups.items():
            self.list.add_widget(wrapped(day, tone='muted', font=14, minimum=36))
            for entry in items:
                expression = pretty(entry['expression'])
                result = display_number(entry['result'], places)
                expression = expression if len(expression) <= 48 else expression[:45] + '…'
                result = result if len(result) <= 44 else result[:41] + '…'
                row = button(expression + '\n= ' + result, lambda ident=entry['id']: app().open_details(ident),
                             size_hint_y=None, height=dp(88), halign='left', padding=(dp(16), dp(8)), font_size=sp(17))
                self.list.add_widget(row)


class DetailsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entry_id = None
        outer = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        outer.add_widget(header('Calculation Details'))
        self.scroll, self.list = scroll_list()
        outer.add_widget(self.scroll)
        self.add_widget(outer)

    def entry(self):
        return next((item for item in app().store.history if item['id'] == self.entry_id), None)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        self.list.clear_widgets()
        item = self.entry()
        if not item:
            self.list.add_widget(wrapped('This calculation is no longer available.', tone='muted'))
            return
        timestamp = datetime.fromisoformat(item['createdAt']).strftime('%d %B %Y • %I:%M:%S %p %z')
        for text, tone, font in [('SAVED CALCULATION', 'accent', 13), (timestamp, 'muted', 14),
                                 ('Expression', 'muted', 14), (pretty(item['expression']), 'fg', 23),
                                 ('Result', 'muted', 14), (display_number(item['result'], app().store.settings['decimalPlaces']), 'fg', 30),
                                 ('Full precision', 'muted', 14), (item['result'], 'fg', 16)]:
            self.list.add_widget(wrapped(text, tone=tone, font=font))
        self.list.add_widget(button('Copy Result', lambda: app().copy(item['result']), role='primary', size_hint_y=None, height=dp(52)))
        self.list.add_widget(button('Use Expression', lambda: app().open_calculator(item['expression']), size_hint_y=None, height=dp(52)))
        self.list.add_widget(button('Delete', self.ask_delete, role='danger', size_hint_y=None, height=dp(52)))

    def ask_delete(self):
        if self.entry():
            app().confirm('Delete calculation?', 'This saved calculation will be permanently removed.', self.delete, 'Delete')

    def delete(self):
        app().check_save(app().store.delete(self.entry_id))
        app().back()


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        outer = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        outer.add_widget(header('Settings'))
        self.scroll, self.list = scroll_list()
        outer.add_widget(self.scroll)
        self.add_widget(outer)

    def on_pre_enter(self, *_):
        self.refresh()

    def change(self, key, value):
        app().check_save(app().store.preference(key, value))
        if key == 'theme':
            app().apply_theme(value)
        position = self.scroll.scroll_y
        self.refresh()
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', position), 0)

    def refresh(self):
        if not app().store:
            return
        settings = app().store.settings
        self.list.clear_widgets()
        self.list.add_widget(wrapped('Make it yours', font=26))
        self.list.add_widget(wrapped('Appearance', tone='muted', font=14))
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        for theme in ('light', 'dark'):
            row.add_widget(button(theme.title(), lambda choice=theme: self.change('theme', choice),
                                  role='primary' if settings['theme'] == theme else 'normal'))
        self.list.add_widget(row)
        self.list.add_widget(wrapped('Decimal places', font=19))
        self.list.add_widget(wrapped('Round only what you see, from 0 to 10 places. Calculations and copied results keep their full working precision.', tone='muted', font=14))
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        places = settings['decimalPlaces']
        less = button('−', lambda: self.change('decimalPlaces', max(0, places - 1)), size_hint_x=None, width=dp(64), font_size=sp(24))
        less.disabled = places == 0
        more = button('+', lambda: self.change('decimalPlaces', min(10, places + 1)), size_hint_x=None, width=dp(64), font_size=sp(24))
        more.disabled = places == 10
        row.add_widget(less)
        row.add_widget(Text(text=str(places), font_size=sp(26), bold=True))
        row.add_widget(more)
        self.list.add_widget(row)
        self.list.add_widget(wrapped('Calculation history', font=19))
        self.list.add_widget(button('Save History: ' + ('On' if settings['saveHistory'] else 'Off'),
                                    lambda: self.change('saveHistory', not settings['saveHistory']),
                                    role='primary' if settings['saveHistory'] else 'normal', size_hint_y=None, height=dp(52)))
        self.list.add_widget(wrapped('Turning this off prevents new entries. Existing calculations remain until you delete them. Up to 1,000 entries are kept.', tone='muted', font=14))
        clear = button('Clear History', lambda: app().confirm_clear(), role='danger', size_hint_y=None, height=dp(52))
        clear.disabled = not app().store.history
        self.list.add_widget(clear)
        self.list.add_widget(wrapped('Pocket Calculator  •  Version 1.0.0', tone='muted', font=14, minimum=48))
        self.list.add_widget(wrapped('All data stays on this device', tone='accent', font=16))
        self.list.add_widget(wrapped('Offline by design. No account, ads, or network connection required.', tone='muted', font=14))


class PocketCalculatorApp(App):
    palette = DictProperty(DARK)
    title = 'Pocket Calculator'

    def build(self):
        self.store = None
        self.navigation = []
        self.active_popup = None
        self.toast_event = None
        Window.clearcolor = self.palette['bg']
        self.root_layout = FloatLayout()
        self.manager = ScreenManager(transition=SlideTransition(duration=.18))
        for cls, name in ((LaunchScreen, 'launch'), (CalculatorScreen, 'calculator'),
                          (HistoryScreen, 'history'), (DetailsScreen, 'details'), (SettingsScreen, 'settings')):
            self.manager.add_widget(cls(name=name))
        self.root_layout.add_widget(self.manager)
        self.toast = Toast(size_hint=(.92, None), height=dp(56), pos_hint={'center_x': .5}, y=dp(14), opacity=0)
        self.root_layout.add_widget(self.toast)
        Window.bind(on_keyboard=self.on_keyboard)
        return self.root_layout

    def initialize(self):
        if self.store is not None:
            return
        self.store = Store(self.user_data_dir)
        self.apply_theme(self.store.settings['theme'])
        self.open_calculator()
        if self.store.error:
            Clock.schedule_once(lambda dt: self.notify(self.store.error), .4)

    def apply_theme(self, theme):
        self.palette = dict(LIGHT if theme == 'light' else DARK)
        Window.clearcolor = self.palette['bg']

    def go(self, name):
        if name == self.manager.current:
            return
        if self.manager.current != 'launch':
            self.navigation.append(self.manager.current)
        self.manager.transition.direction = 'left'
        self.manager.current = name

    def back(self):
        if self.active_popup:
            self.active_popup.dismiss()
            return True
        if self.manager.current not in ('calculator', 'launch'):
            self.manager.transition.direction = 'right'
            self.manager.current = self.navigation.pop() if self.navigation else 'calculator'
            return True
        return False

    def on_keyboard(self, window, key, *args):
        if key == 27:
            return self.back()
        return False

    def open_calculator(self, expression=None):
        if expression is not None:
            self.manager.get_screen('calculator').load(expression)
        self.navigation = []
        self.manager.transition.direction = 'right' if self.manager.current != 'launch' else 'left'
        self.manager.current = 'calculator'

    def open_details(self, ident):
        self.manager.get_screen('details').entry_id = ident
        self.go('details')

    def notify(self, text):
        self.toast.text = text
        self.toast.opacity = 1
        if self.toast_event:
            self.toast_event.cancel()
        self.toast_event = Clock.schedule_once(lambda dt: setattr(self.toast, 'opacity', 0), 3)

    def copy(self, text):
        try:
            Clipboard.copy(text)
            self.notify('Result copied at full precision')
        except Exception:
            self.notify('Clipboard is unavailable on this device')

    def check_save(self, success):
        if not success:
            self.notify(self.store.error or 'Could not save changes')
        return success

    def confirm(self, title, message, action, confirm_text='Clear History'):
        if self.active_popup:
            return
        content = ToneBox(orientation='vertical', spacing=dp(18), padding=dp(16))
        label = Text(text=message, halign='left', valign='middle')
        label.bind(size=lambda obj, val: setattr(obj, 'text_size', val))
        content.add_widget(label)
        actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        popup = Popup(title=title, title_color=self.palette['fg'], title_size=sp(19),
                      content=content, size_hint=(.92, None), height=dp(270),
                      background='', background_color=self.palette['surface'],
                      separator_color=self.palette['accent'], auto_dismiss=False)
        actions.add_widget(button('Cancel', popup.dismiss))
        def accept():
            popup.dismiss()
            action()
        actions.add_widget(button(confirm_text, accept, role='danger'))
        content.add_widget(actions)
        popup.bind(on_dismiss=lambda *_: setattr(self, 'active_popup', None))
        self.active_popup = popup
        popup.open()

    def confirm_clear(self):
        if not self.store.history:
            self.notify('No calculations to clear')
            return
        self.confirm('Clear all history?', 'All saved calculations will be removed. This cannot be undone.', self.clear_history)

    def clear_history(self):
        success = self.check_save(self.store.clear())
        for name in ('history', 'settings', 'details'):
            self.manager.get_screen(name).refresh()
        if success:
            self.notify('History cleared')

    def on_pause(self):
        return True


if __name__ == '__main__':
    PocketCalculatorApp().run()
