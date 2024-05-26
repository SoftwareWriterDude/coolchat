#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk
import socket
import socks#PySocks
import threading
import ssl

#unfortunately i cant find a way to gracefully exit this thread, 
#the thread will run until its told to stop but must wait for data to break out of its loop
def receive_messages(stop_event, message_box):
    try:
        global sock
        while not stop_event.is_set():
            data = sock.recv(1024).decode('utf-8')
            if not data:
                break
            Gtk.main_iteration_do(False)
            display_message(message_box, data)
    except Exception as e:
        print("receive_messages: ", e)

def send_message(widget, message_box, message_entry):
    global sock
    #print("send_messaged called\n")
    message = message_entry.get_text()
    if message.strip() != "":
        try:
            sock.sendall(bytes(message + '\n', 'utf-8'))
            message_entry.set_text("")  # Clear the message entry field
        except Exception as e:
            display_message(message_box, f"Error sending message: {e}", e)

def disconnect_clicked(button, connect_button, disconnect_button, send_button):
    #connect_button.set_sensitive(True)
    if disconnect_button.get_sensitive() == True:
        disconnect_button.set_sensitive(False)
    if connect_button.get_sensitive() == False:
        connect_button.set_sensitive(True)
    if send_button.get_sensitive() == True:
        send_button.set_sensitive(False)

    global t
    global sock
    if t is None or not t.is_alive():
        stop_event.set()
        sock.close()
        t.join()

def connect_clicked(button, message_box, message_entry, ip_entry, port_entry, connect_button, disconnect_button, send_button):
    if disconnect_button.get_sensitive() == False:
        disconnect_button.set_sensitive(True)
    if connect_button.get_sensitive() == True:
        connect_button.set_sensitive(False)
    if send_button.get_sensitive() == False:
        send_button.set_sensitive(True)
    ip = ip_entry.get_text()
    port = int(port_entry.get_text())
    global useTor
    if useTor == True:
        #try to connect to a running instance of Tor, either the daemon or the TBB
        proxy_ports = [9050, 9150]
        for port in proxy_ports:
            try:
                print("Trying to connect to tor, please wait...\n")
                socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", port)
                socket.socket = socks.socksocket
                break
            except Exception as e:
                display_message(message_box, f"Failed to connect to proxy on port {port}: {e}")
                return

            display_message(message_box, f"Proxy connection successful on port {port}")
    try:
        global sock
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sock = context.wrap_socket(sock, server_hostname=ip)
        #sock.setblocking(False)  # Set socket to non-blocking mode
        sock.connect((ip, port))
        cert = sock.getpeercert(True)
        cert_info = ssl.DER_cert_to_PEM_cert(cert)
        display_message(message_box, str(cert_info))
        msg = message_entry.get_text()
        stop_event.clear()

        global t
        t = threading.Thread(target=receive_messages, args=(stop_event, message_box,))
        t.start()

    except Exception as e:
        print("Error connecting:", e)
        display_message(message_box, str(e))

def display_message(message_box, message):
    GLib.idle_add(append_message, message_box, message)

def append_message(message_box, message):
    buffer = message_box.get_buffer()
    end_iter = buffer.get_end_iter()
    buffer.insert(end_iter, " " + message + "\n")#insert a space before the text because its easier than fucking around with padding in gtk in python lol
    end_mark = buffer.create_mark(None, end_iter, left_gravity=True)
    message_box.scroll_to_mark(end_mark, 0.0, use_align=False, xalign=0.5, yalign=1.0)
    
def on_check_button_toggled(button):
    if button.get_active():
        useTor = True
    else:
        useTor = False

def on_window_destroy(window):
    stop_event.set()
    Gtk.main_quit()

def on_key_press_event(widget, event):
    if event.keyval == Gdk.KEY_Return:
        send_message(widget, )

stop_event = threading.Event()
useTor = True
sock = None
t = None

def main():
    Gtk.init(None)

    window = Gtk.Window(title="Cool Chat")
    window.connect("destroy", on_window_destroy)
    window.set_icon_from_file("icon64.png")
    window.set_border_width(10)
    window.set_default_size(1024, 768)

    message_box = Gtk.TextView()
    message_box.set_editable(False)
    message_box.set_wrap_mode(Gtk.WrapMode.WORD)
    scroll = Gtk.ScrolledWindow()
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)
    scroll.add(message_box)

    scroll.set_margin_top(1)
    scroll.set_margin_bottom(1)
    scroll.set_margin_start(1)

    ip_entry = Gtk.Entry()
    ip_entry.set_placeholder_text("IP Address")

    port_entry = Gtk.Entry()
    port_entry.set_placeholder_text("Port")

    message_entry = Gtk.Entry()
    message_entry.set_placeholder_text("Type your message here...")
    message_entry.connect("activate", send_message, message_box, message_entry)
    #message_entry.connect("key-press-event", send_message, message_box, message_entry)

    connect_button = Gtk.Button(label="Connect")
    disconnect_button = Gtk.Button(label="Disconnect")
    send_button = Gtk.Button(label="Send")

    send_button.connect("clicked", send_message, message_box, message_entry)
    #send_button.set_size_request(50, -1)
    send_button.set_sensitive(False)

    disconnect_button.connect("clicked", disconnect_clicked, connect_button, disconnect_button, send_button)
    disconnect_button.set_sensitive(False)

    connect_button.connect("clicked", connect_clicked, message_box, message_entry, ip_entry, port_entry, connect_button, disconnect_button, send_button)
    connect_button.set_sensitive(True)

    torCheckBox = Gtk.CheckButton(label="Tor")
    torCheckBox.connect("toggled", on_check_button_toggled)
    torCheckBox.set_active(True)

    grid = Gtk.Grid()
    grid.set_column_spacing(10)
    grid.set_row_spacing(10)
    grid.attach(ip_entry, 0, 0, 1, 1)
    grid.attach_next_to(port_entry, ip_entry, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach_next_to(torCheckBox, port_entry, Gtk.PositionType.RIGHT,1,1)
    grid.attach_next_to(connect_button, torCheckBox, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach_next_to(disconnect_button, connect_button, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach(scroll, 0, 1, 5, 1)
    grid.attach(message_entry, 0, 2, 4, 1)
    grid.attach_next_to(send_button, message_entry, Gtk.PositionType.RIGHT, 1, 1)

    # Load CSS from file
    #css_provider = Gtk.CssProvider()
    #css_provider.load_from_path('style.css')

    # Apply the CSS to the current screen
    #screen = Gdk.Screen.get_default()
    #style_context = Gtk.StyleContext()
    #style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # Load CSS file
    css_provider = Gtk.CssProvider()
    css_provider.load_from_path("style.css")

    context = message_box.get_style_context()
    context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    window.add(grid)

    window.show_all()

    Gtk.main()

if __name__ == "__main__":
    main()