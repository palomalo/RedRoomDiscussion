from tkinter import *
import os
from tkinter import messagebox
from AppFiles.manager.db_topics import Database

def Signup():  # This is the signup definition,
    global pwordE  # These globals just make the variables global to the entire script, meaning any definition can use them
    global nameE
    global roots

    roots = Tk()  # This creates the window, just a blank one.
    roots.title('Signup')  # This renames the title of said window to 'signup'
    intruction = Label(roots,
                       text='Please Enter new Credidentials\n')  # This puts a label, so just a piece of text saying 'please enter blah'
    intruction.grid(row=0, column=0,
                    sticky=E)  # This just puts it in the window, on row 0, col 0. If you want to learn more look up a tkinter tutorial :)

    nameL = Label(roots, text='New Username: ')  # This just does the same as above, instead with the text new username.
    pwordL = Label(roots, text='New Password: ')  # ^^
    nameL.grid(row=1, column=0,
               sticky=W)  # Same thing as the instruction var just on different rows. :) Tkinter is like that.
    pwordL.grid(row=2, column=0, sticky=W)  # ^^

    nameE = Entry(roots)  # This now puts a text box waiting for input.
    pwordE = Entry(roots,
                   show='*')  # Same as above, yet 'show="*"' What this does is replace the text with *, like a password box :D
    nameE.grid(row=1, column=1)  # You know what this does now :D
    pwordE.grid(row=2, column=1)  # ^^

    signupButton = Button(roots, text='Signup',
                          command=FSSignup)  # This creates the button with the text 'signup', when you click it, the command 'fssignup' will run. which is the def
    signupButton.grid(columnspan=2, sticky=W)
    roots.mainloop()  # This just makes the window keep open, we will destroy it soon


def FSSignup():
    with open(creds, 'w') as f:  # Creates a document using the variable we made at the top.
        f.write(
            nameE.get())  # nameE is the variable we were storing the input to. Tkinter makes us use .get() to get the actual string.
        f.write('\n')  # Splits the line so both variables are on different lines.
        f.write(pwordE.get())  # Same as nameE just with pword var
        f.close()  # Closes the file

    roots.destroy()  # This will destroy the signup window. :)
    Login()  # This will move us onto the login definition :D


def Login():
    global nameEL
    global pwordEL  # More globals :D
    global rootA

    rootA = Tk()  # This now makes a new window.
    rootA.title('Login')  # This makes the window title 'login'
    rootA.geometry('700x350')
    intruction = Label(rootA, text='Please Login\n')  # More labels to tell us what they do
    intruction.grid(sticky=E)  # Blahdy Blah

    nameL = Label(rootA, text='Username: ')  # More labels
    pwordL = Label(rootA, text='Password: ')  # ^
    nameL.grid(row=1, sticky=W)
    pwordL.grid(row=2, sticky=W)

    nameEL = Entry(rootA)  # The entry input
    pwordEL = Entry(rootA, show='*')
    nameEL.grid(row=1, column=1)
    pwordEL.grid(row=2, column=1)

    loginB = Button(rootA, text='Login',
                    command=CheckLogin)  # This makes the login button, which will go to the CheckLogin def.
    loginB.grid(columnspan=2, sticky=W)

    rmuser = Button(rootA, text='Delete User', fg='red',
                    command=DelUser)  # This makes the deluser button. blah go to the deluser def.
    rmuser.grid(columnspan=2, sticky=W)

    rootA.mainloop()


def CheckLogin():
    def populate_list():
        parts_list.delete(0, END)
        for row in db.fetch():
            parts_list.insert(END, row)

    def add_item():
        if topic_name.get() == '' or topic_text.get() == '':
            messagebox.showerror('Required Fields', 'Please include all fields')
            return

        db.insert(topic_name.get(), topic_text.get())
        parts_list.delete(0, END)
        parts_list.insert(END, (topic_name.get(), topic_text.get()))
        clear_text()
        populate_list()

    def select_item(event):
        try:
            global selected_item

            index = parts_list.curselection()[0]
            selected_item = parts_list.get(index)
            chat_btn.grid()

            part_entry.delete(0, END)
            part_entry.insert(END, selected_item[1])
            customer_entry.delete(0, END)
            customer_entry.insert(END, selected_item[2])

        except IndexError:
            pass

    def remove_item():
        db.remove(selected_item[0])
        clear_text()
        populate_list()

    def update_item():
        db.update(selected_item[0], topic_name.get(), topic_text.get())
        populate_list()

    def send_msg():
        print("send send send")

    def start_chat():

        app.destroy()
        chat = Tk()
        chat.title(selected_item)
        chat.geometry('700x450')

        chatMsg = StringVar()
        chat_label = Label(chat, text='chat Msg', font=('bold', 14), pady=20)
        chat_label.grid(row=0, column=0, sticky=W)
        chat_entry = Entry(chat, textvariable=chatMsg)
        chat_entry.grid(row=0, column=1)

        chat_btn_send = Button(chat, text='send Msg', width=12, command=send_msg)
        chat_btn_send.grid(row=0, column=2, pady=20)

        # Start program
        chat.mainloop()

    def clear_text():
        part_entry.delete(0, END)
        customer_entry.delete(0, END)

    with open(creds) as f:
        data = f.readlines()  # This takes the entire document we put the info into and puts it into the data variable
        uname = data[0].rstrip()  # Data[0], 0 is the first line, 1 is the second and so on.
        pword = data[1].rstrip()  # Using .rstrip() will remove the \n (new line) word from before when we input it

    if nameEL.get() == uname and pwordEL.get() == pword:  # Checks to see if you entered the correct data.
        '''r = Tk()  # Opens new window
        r.title(':D')
        r.geometry('1500x350')  # Makes the window a certain size
        rlbl = Label(r, text='\n[+] Logged In')  # "logged in" label

        rlbl.pack()  # Pack is like .grid(), just different
        rootA.destroy()
        r.mainloop()'''
        rootA.destroy()
        app = Tk()

        # topic name
        topic_name = StringVar()
        part_label = Label(app, text='topic Name', font=('bold', 14), pady=20)
        part_label.grid(row=0, column=0, sticky=W)
        part_entry = Entry(app, textvariable=topic_name)
        part_entry.grid(row=0, column=1)
        # topic text
        topic_text = StringVar()
        customer_label = Label(app, text='topic text', font=('bold', 14))
        customer_label.grid(row=0, column=2, sticky=W)
        customer_entry = Entry(app, textvariable=topic_text)
        customer_entry.grid(row=0, column=3)

        # Parts List (Listbox)
        parts_list = Listbox(app, height=8, width=50, border=0)
        parts_list.grid(row=3, column=0, columnspan=3, rowspan=6, pady=20, padx=20)
        # Create scrollbar
        scrollbar = Scrollbar(app)
        scrollbar.grid(row=3, column=3)
        # Set scroll to listbox
        parts_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=parts_list.yview)
        # Bind select
        parts_list.bind('<<ListboxSelect>>', select_item)

        # Buttons
        add_btn = Button(app, text='Add topic', width=12, command=add_item)
        add_btn.grid(row=2, column=0, pady=20)

        remove_btn = Button(app, text='Remove topic', width=12, command=remove_item)
        remove_btn.grid(row=2, column=1)

        update_btn = Button(app, text='Update topic', width=12, command=update_item)
        update_btn.grid(row=2, column=2)

        clear_btn = Button(app, text='Clear topic input', width=12, command=clear_text)
        clear_btn.grid(row=2, column=3)

        chat_btn = Button(app, text='start Chat', width=12, command=start_chat)
        chat_btn.grid(row=2, column=4)
        chat_btn.grid_remove()

        app.title('Topic Manager')
        app.geometry('700x550')

        # Populate data
        populate_list()

        # Start program
        app.mainloop()

    else:
        r = Tk()
        r.title('Login Failed:')
        r.geometry('450x450')
        rlbl = Label(r, text='\n[!] Invalid Login')
        rlbl.pack()
        r.mainloop()


def DelUser():
    os.remove(creds)  # Removes the file
    rootA.destroy()  # Destroys the login window
    Signup()  # And goes back to the start!


if os.path.isfile(creds):
    Login()
else:  # This if else statement checks to see if the file exists. If it does it will go to Login, if not it will go to Signup :)
    Signup()