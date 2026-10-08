# -*- coding: utf-8 -*-
#
# Control Your Tabs, a plugin for pluma
# Switch between tabs using Ctrl-Tab / Ctrl-Shift-Tab and
# Ctrl-PageUp / Ctrl-PageDown
# v0.1.2
#
# Ctrl-Tab / Ctrl-Shift-Tab switch tabs in most recently used order.
# Ctrl-PageUp / Ctrl-PageDown switch tabs in tabbar order.
#
# Inspired by:
#     TabSwitch by Elia Sarti
#     TabPgUpPgDown by Eran M.
#     the pluma Documents panel
#
# Copyright (C) 2010 Jeffery To <jeffery.to@gmail.com>
# https://github.com/jefferyto/gedit-control-your-tabs
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# -*- coding: utf-8 -*-

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Pluma', '1.0')
from gi.repository import GObject, Gtk, Gdk, GLib, Gio, Pluma, GdkPixbuf
from gettext import gettext as _
from xml.sax.saxutils import escape

class ControlYourTabsWindowHelper:
    HANDLER_IDS = 'ControlYourTabsPluginHandlerIds'
    SELECTED_TAB_COLUMN = 3

    META_KEYS = ('Shift_L', 'Shift_R',
                 'Control_L', 'Control_R',
                 'Meta_L', 'Meta_R',
                 'Super_L', 'Super_R',
                 'Hyper_L', 'Hyper_R',
                 'Alt_L', 'Alt_R')

    MAX_DOC_NAME_LENGTH = 60
    MAX_TAB_WINDOW_HEIGHT = 250

    def __init__(self, plugin, window):
        stack = []

        tabwin = Gtk.Window(type=Gtk.WindowType.POPUP)
        tabwin.set_transient_for(window)
        tabwin.set_destroy_with_parent(True)
        tabwin.set_accept_focus(False)
        tabwin.set_decorated(False)
        tabwin.set_resizable(False)
        tabwin.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        tabwin.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        tabwin.set_skip_taskbar_hint(False)
        tabwin.set_skip_pager_hint(False)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.show()

        tabwin.add(sw)

        model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, object, bool)

        view = Gtk.TreeView(model=model)
        view.set_enable_search(False)
        view.set_headers_visible(False)
        view.show()

        sw.add(view)

        col = Gtk.TreeViewColumn(title=_('Documents'))
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        cell = Gtk.CellRendererPixbuf()
        col.pack_start(cell, False)
        col.add_attribute(cell, 'pixbuf', 0)
        cell = Gtk.CellRendererText()
        col.pack_start(cell, True)
        col.add_attribute(cell, 'markup', 1)

        view.append_column(col)

        sel = view.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)

        self.connect_handlers(model, ('row-changed',), 'model', view, sel)

        self._tabbing = False
        self._paging = False
        self._ctrl_l = False
        self._ctrl_r = False
        self._stack = stack
        self._model = model
        self._view = view
        self._window = window
        self._plugin = plugin

        cur = window.get_active_tab()
        if cur:
            for tab in cur.get_parent().get_children():
                self.window_tab_added(window, tab, stack, model)
            self.window_active_tab_changed(window, cur, stack, model)

        self.connect_handlers(window, ('tab-added', 'tab-removed', 'active-tab-changed', 'key-press-event', 'key-release-event', 'focus-out-event'), 'window', stack, model)

    def deactivate(self):
        self.disconnect_handlers(self._window)
        self.end_switching()
        self._view.get_toplevel().destroy()
        self.disconnect_handlers(self._model)

        self._tabbing = None
        self._paging = None
        self._ctrl_l = None
        self._ctrl_r = None
        self._stack = None
        self._model = None
        self._view = None
        self._window = None
        self._plugin = None

    def update_ui(self):
        pass

    def model_row_changed(self, model, path, iter, view, sel):
        if model[path][self.SELECTED_TAB_COLUMN]:
            sel.select_path(path)
            view.scroll_to_cell(path, None, False, 0, 0)
        else:
            sel.unselect_path(path)

    def window_tab_added(self, window, tab, stack, model):
        if tab not in stack:
            stack.append(tab)
            model.append([None, self.tab_get_name(tab), tab, False])

        self.connect_handlers(tab, ('notify::name', 'notify::state'), self.sync_icon_and_name, stack, model)

    def window_tab_removed(self, window, tab, stack, model):
        self.disconnect_handlers(tab)
        if tab in stack:
            model.remove(model.get_iter(stack.index(tab)))
            stack.remove(tab)

    def window_active_tab_changed(self, window, tab, stack, model):
        if not self._tabbing and not self._paging:
            if tab in stack:
                model.remove(model.get_iter(stack.index(tab)))
                stack.remove(tab)

            for row in model:
                row[self.SELECTED_TAB_COLUMN] = False

            stack.insert(0, tab)
            model.insert(0, [None, self.tab_get_name(tab), tab, True])

    def sync_icon_and_name(self, tab, pspec, stack, model):
        if tab in stack:
            path = stack.index(tab)
            model[path][1] = self.tab_get_name(tab)

    def tab_get_name(self, tab):
        doc = tab.get_document()
        name = doc.get_short_name_for_display()
        docname = self.str_middle_truncate(name, self.MAX_DOC_NAME_LENGTH)

        if doc.get_modified():
            tab_name = '<i>%s</i>' % escape(docname)
        else:
            tab_name = docname

        if doc.get_readonly():
            tab_name += ' [<i>%s</i>]' % escape(_('Read Only'))

        return tab_name

    def window_key_press_event(self, window, event, stack, model):
        key = Gdk.keyval_name(event.keyval)
        state = event.state & Gtk.accelerator_get_default_mod_mask()

        if key == 'Control_L':
            self._ctrl_l = True
        if key == 'Control_R':
            self._ctrl_r = True

        if key in self.META_KEYS or not (state & Gdk.ModifierType.CONTROL_MASK):
            return False

        is_ctrl = state == Gdk.ModifierType.CONTROL_MASK
        is_ctrl_shift = state == (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        is_tab_key = key in ('ISO_Left_Tab', 'Tab')
        is_page_key = key in ('Page_Up', 'Page_Down')
        is_up_dir = key in ('ISO_Left_Tab', 'Page_Up')

        if not (((is_ctrl or is_ctrl_shift) and is_tab_key) or (is_ctrl and is_page_key)):
            self.end_switching()
            return False

        cur = window.get_active_tab()
        if is_tab_key:
            tabs = stack
        else:
            tabs = cur.get_parent().get_children()
        tlen = len(tabs)

        if cur and tlen > 1 and cur in tabs:
            if is_up_dir:
                i = -1
            else:
                i = 1
            next_tab = tabs[(tabs.index(cur) + i) % tlen]

            model[stack.index(cur)][self.SELECTED_TAB_COLUMN] = False
            model[stack.index(next_tab)][self.SELECTED_TAB_COLUMN] = True

            if is_tab_key:
                view = self._view
                tabwin = view.get_toplevel()
                _minimum, natural_req = view.get_preferred_size()
                h = natural_req.height if hasattr(natural_req, 'height') else 200
                tabwin.set_size_request(-1, min(h, self.MAX_TAB_WINDOW_HEIGHT))
                tabwin.present()
                self._tabbing = True
            else:
                self._paging = True

            window.set_active_tab(next_tab)

        return True

    def window_key_release_event(self, window, event, stack, model):
        key = Gdk.keyval_name(event.keyval)
        if key == 'Control_L':
            self._ctrl_l = False
        if key == 'Control_R':
            self._ctrl_r = False

        if not self._ctrl_l and not self._ctrl_r:
            self.end_switching()

    def window_focus_out_event(self, window, event, stack, model):
        self.end_switching()

    def end_switching(self):
        if self._tabbing or self._paging:
            self._tabbing = False
            self._paging = False
            self._ctrl_l = False
            self._ctrl_r = False
            self._view.get_toplevel().hide()

            window = self._window
            tab = window.get_active_tab()
            if tab:
                self.window_active_tab_changed(window, tab, self._stack, self._model)

    def connect_handlers(self, obj, signals, m, *args):
        l_ids = getattr(obj, '_handler_ids', [])
        for signal in signals:
            if isinstance(m, str):
                method = getattr(self, m + '_' + signal.replace('-', '_'))
            else:
                method = m
            l_ids.append(obj.connect(signal, method, *args))
        obj._handler_ids = l_ids

    def disconnect_handlers(self, obj):
        l_ids = getattr(obj, '_handler_ids', None)
        if l_ids:
            for l_id in l_ids:
                obj.disconnect(l_id)
            obj._handler_ids = None

    def str_middle_truncate(self, string, truncate_length):
        delimiter = '…'
        delimiter_length = len(delimiter)
        if truncate_length < (delimiter_length + 2):
            return string
        n_chars = len(string)
        if n_chars <= truncate_length:
            return string

        num_left_chars = int((truncate_length - delimiter_length) / 2)
        right_offset = n_chars - truncate_length + num_left_chars + delimiter_length
        return string[:num_left_chars] + delimiter + string[right_offset:]


class ControlYourTabsPlugin(GObject.Object, Pluma.WindowActivatable):
    __gtype_name__ = "ControlYourTabsPlugin"
    window = GObject.property(type=Pluma.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._instances = {}

    def do_activate(self):
        self._instances[self.window] = ControlYourTabsWindowHelper(self, self.window)

    def do_deactivate(self):
        if self.window in self._instances:
            self._instances[self.window].deactivate()
            del self._instances[self.window]

    def do_update_state(self):
        if self.window in self._instances:
            self._instances[self.window].update_ui()
