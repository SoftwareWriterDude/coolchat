#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk
import socket
import socks#PySocks
import threading
import ssl
import csv

def on_serverlist_button_clicked(button, listbox):
    # Open the CSV file and read its contents
    with open('serverlist.csv', 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row:
                # Combine the 3 values of each row to create the button label
                label_text = '    '.join(row[:3])
                # Create a new button for each item in the CSV
                item = Gtk.Button(label=label_text)  # Specify the label keyword argument
                item.set_margin_bottom(5)
                item.connect("clicked", on_item_clicked, str(row[1]), str(row[2]))
                listbox.add(item)
            listbox.show_all()

def on_item_clicked(event, ip, port):
    print("Item clicked: ")
    global ip_entry
    global port_entry
    ip_entry.set_text(ip)
    port_entry.set_text(port)

# The server list CSV viwer window
def create_serverlist_window(event):
    window = Gtk.Window(title="Server List CSV")
    window.set_default_size(800, 600)

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    window.add(main_box)

    listbox = Gtk.ListBox()

    scroll = Gtk.ScrolledWindow()
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)
    scroll.add(listbox)

    scroll.set_margin_top(1)
    scroll.set_margin_bottom(1)
    scroll.set_margin_start(1)

    main_box.pack_start(scroll, True, True, 0)

    button = Gtk.Button.new_with_label("Load CSV")
    button.connect("clicked", on_serverlist_button_clicked, listbox)
    main_box.pack_start(button, False, False, 0)
    window.show_all()

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
                socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", port)
                socket.socket = socks.socksocket
                break
            except Exception as e:
                display_message(message_box, f"Failed to set proxy on port {port}: {e}")
                print("Failed to set Tor proxy. Make sure the Tor daemon or TBB is running\n")
                return

    try:
        global sock
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sock = context.wrap_socket(sock, server_hostname=ip)
        sock.settimeout(10)
        sock.connect((ip, port))
        sock.settimeout(None)
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
        connect_button.set_sensitive(True)
        disconnect_button.set_sensitive(False)
        display_message(message_box, "Connection failed, Make sure you typed the location correctly and if using Tor make sure a Tor instance is running.")
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
    global useTor
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

# Global variables for ip and port
ip_entry = Gtk.Entry()
port_entry = Gtk.Entry()

def main():
    Gtk.init(None)

    window = Gtk.Window(title="Cool Chat")
    window.connect("destroy", on_window_destroy)
    window.set_icon_from_file("icon64.png")
    window.set_border_width(10)
    window.set_default_size(800, 600)

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

    #ip_entry = Gtk.Entry()
    global ip_entry
    ip_entry.set_placeholder_text("IP Address")

    #port_entry = Gtk.Entry()
    global port_entry
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

    # Menu Bar
    menubar = Gtk.MenuBar()
    file_menu = Gtk.Menu()
    file_menu_item = Gtk.MenuItem(label="File")
    file_menu_item.set_submenu(file_menu)
    server_list_item = Gtk.MenuItem(label="Server List")
    server_list_item.connect("activate", create_serverlist_window)
    file_menu.append(server_list_item)
    menubar.append(file_menu_item)


    # Setup the GUI elements, attach(column, row, width, height)
    grid = Gtk.Grid()
    grid.set_column_spacing(5)
    grid.set_row_spacing(5)
    grid.attach(menubar, 0, 0, 5, 1)
    grid.attach(ip_entry, 0, 1, 1, 1)
    grid.attach_next_to(port_entry, ip_entry, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach_next_to(torCheckBox, port_entry, Gtk.PositionType.RIGHT,1,1)
    grid.attach_next_to(connect_button, torCheckBox, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach_next_to(disconnect_button, connect_button, Gtk.PositionType.RIGHT, 1, 1)
    grid.attach(scroll, 0, 2, 5, 1)
    grid.attach(message_entry, 0, 3, 4, 1)
    grid.attach_next_to(send_button, message_entry, Gtk.PositionType.RIGHT, 1, 1)

    # Load CSS file
    css_provider = Gtk.CssProvider()
    css_provider.load_from_path("style.css")

    # Choose which parts of the UI we want styled by the CSS
    # message_box
    msg_boxContext = message_box.get_style_context()
    msg_boxContext.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    # message_entry
    msg_entryContext = message_entry.get_style_context()
    msg_entryContext.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    # menubar
    menubar_context = menubar.get_style_context()
    menubar_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    window.add(grid)

    window.show_all()

    Gtk.main()

if __name__ == "__main__":
    main()
