import tkinter
import cv2
import PIL.Image, PIL.ImageTk
from functools import partial
import threading
import time
import imutils
import os
import queue

# --- Path to the assets folder ---
ASSETS_PATH = "assets"

# --- Video sources with updated paths ---
video_sources = [
    os.path.join(ASSETS_PATH, "1.mp4"),
    os.path.join(ASSETS_PATH, "lbw.mp4"),
    os.path.join(ASSETS_PATH, "2.mp4"),
    os.path.join(ASSETS_PATH, "3.mp4"),
    os.path.join(ASSETS_PATH, "4.mp4"),
    os.path.join(ASSETS_PATH, "5.mp4"),
    os.path.join(ASSETS_PATH, "6.mp4"),
    os.path.join(ASSETS_PATH, "7.mp4"),
    os.path.join(ASSETS_PATH, "8.mp4"),
    os.path.join(ASSETS_PATH, "9.mp4"),
    os.path.join(ASSETS_PATH, "10.mp4"),
    os.path.join(ASSETS_PATH, "11.mp4"),
    os.path.join(ASSETS_PATH, "12.mp4")
]

current_angle_index = 0
stream = cv2.VideoCapture(video_sources[current_angle_index])
flag = True

# --- State variables and thread-safe queue for smooth video ---
is_auto_detecting = False
detection_thread = None
stump_box = None
selection_rect = None
detection_start_frame = None # Frame to start analysis from
frame_queue = queue.Queue(maxsize=10) # Queue to safely pass frames between threads

# --- NEW: Variables for object tracking and prediction ---
tracker = None
initial_frame_for_tracker = None
ball_positions = [] # To store recent ball positions for trajectory calculation

def stop_auto_detection():
    """Function to stop the auto-detection thread."""
    global is_auto_detecting
    is_auto_detecting = False
    while not frame_queue.empty():
        try:
            frame_queue.get_nowait()
        except queue.Empty:
            continue

def play(speed):
    """Plays the video forward or backward at a given speed."""
    stop_auto_detection()
    global flag, stump_box, tracker
    print(f"You clicked on play. Speed is {speed}")
    canvas.delete("message")

    frame1 = stream.get(cv2.CAP_PROP_POS_FRAMES)
    stream.set(cv2.CAP_PROP_POS_FRAMES, frame1 + speed)

    grabbed, frame = stream.read()
    if not grabbed:
        change_angle(True)
        return

    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)

    if tracker:
        success, box = tracker.update(frame)
        if success:
            (x, y, w, h) = [int(v) for v in box]
            stump_box = (x, y, w, h)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
    elif stump_box:
        sx, sy, sw, sh = stump_box
        cv2.rectangle(frame, (sx, sy), (sx + sw, sy + sh), (255, 0, 0), 2)

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))

    canvas.image = photo
    canvas.create_image(0, 0, image=photo, anchor=tkinter.NW)

    if flag:
        canvas.create_text(134, 26, fill="black", font="Times 26 bold", text="Decision Pending")
    flag = not flag

def show_final_decision(decision):
    """Callback function to show the final out/not out image without freezing UI."""
    decision_img_name = "out.png" if decision == 'out' else "not_out.png"
    decision_img_path = os.path.join(ASSETS_PATH, decision_img_name)
    frame = cv2.imread(decision_img_path)
    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
    canvas.image = photo
    canvas.create_image(0, 0, image=photo, anchor=tkinter.NW)

def pending(decision):
    """Displays pending and schedules the final decision to avoid freezing."""
    pending_img_path = os.path.join(ASSETS_PATH, "pending.png")
    frame = cv2.imread(pending_img_path)
    frame = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame))
    canvas.image = photo
    canvas.create_image(0, 0, image=photo, anchor=tkinter.NW)
    
    window.after(1500, lambda: show_final_decision(decision))

def out():
    stop_auto_detection()
    pending("out")
    print("Player is out")

def not_out():
    stop_auto_detection()
    pending("not out")
    print("Player is not out")

def change_angle(force_next=False):
    global current_angle_index, stream, stump_box, selection_rect, tracker
    stop_auto_detection()
    stump_box = None
    tracker = None
    canvas.delete(selection_rect)
    selection_rect = None

    if force_next:
        current_angle_index = (current_angle_index + 1) % len(video_sources)
    stream.release()
    stream = cv2.VideoCapture(video_sources[current_angle_index])
    print(f"Switched to angle: {video_sources[current_angle_index]}")
    play(0)

def cycle_angle():
    global current_angle_index
    current_angle_index = (current_angle_index + 1) % len(video_sources)
    change_angle()

# --- Mouse events for selecting stump area ---
def on_mouse_press(event):
    global selection_rect
    canvas.delete(selection_rect)
    canvas.x = event.x
    canvas.y = event.y

def on_mouse_drag(event):
    global selection_rect
    if selection_rect:
        canvas.delete(selection_rect)
    selection_rect = canvas.create_rectangle(canvas.x, canvas.y, event.x, event.y, outline='red', width=2)

def on_mouse_release(event):
    """Initializes tracker after user selects stump area."""
    global stump_box, tracker, initial_frame_for_tracker
    x1, y1, x2, y2 = min(canvas.x, event.x), min(canvas.y, event.y), max(canvas.x, event.x), max(canvas.y, event.y)
    stump_box = (x1, y1, x2-x1, y2-y1)

    if initial_frame_for_tracker is not None:
        tracker = cv2.TrackerKCF_create()
        tracker.init(initial_frame_for_tracker, stump_box)
        print(f"Stump area selected at: {stump_box} and tracker initialized.")
    else:
        print("Error: Initial frame for tracker was not captured.")
        return

    canvas.unbind("<ButtonPress-1>")
    canvas.unbind("<B1-Motion>")
    canvas.unbind("<ButtonRelease-1>")
    canvas.delete("message")
    canvas.create_text(SET_WIDTH/2, SET_HEIGHT-20, fill="green", font="Times 14 bold", text="Stump area locked. Analyzing...", tag="message")
    
    start_auto_detection()

def select_stumps():
    """Initiates the stump selection process."""
    global detection_start_frame, initial_frame_for_tracker, tracker
    stop_auto_detection()
    tracker = None
    detection_start_frame = stream.get(cv2.CAP_PROP_POS_FRAMES)
    
    grabbed, frame = stream.read()
    if not grabbed: return
    stream.set(cv2.CAP_PROP_POS_FRAMES, detection_start_frame)
    initial_frame_for_tracker = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
    
    canvas.delete("message")
    canvas.create_text(SET_WIDTH/2, SET_HEIGHT-20, fill="yellow", font="Times 14 bold", text="Click and drag to select the stump area", tag="message")
    canvas.bind("<ButtonPress-1>", on_mouse_press)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_release)

def auto_detect_out_logic():
    """Processes video, predicts ball trajectory, and then decides."""
    global stream, is_auto_detecting, stump_box, detection_start_frame, tracker, ball_positions
    
    ball_positions.clear()
    
    fps = stream.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps > 60: fps = 30
    slow_motion_multiplier = 2.5
    delay = (1 / fps) * slow_motion_multiplier

    if detection_start_frame is not None:
        stream.set(cv2.CAP_PROP_POS_FRAMES, detection_start_frame)
    else:
        stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    final_decision = "not_out"
    prediction_made = False

    while is_auto_detecting and stream.isOpened():
        grabbed, frame = stream.read()
        if not grabbed: break

        frame_copy = imutils.resize(frame, width=SET_WIDTH, height=SET_HEIGHT)
        
        if tracker:
            success, box = tracker.update(frame_copy)
            if success:
                stump_box = tuple(int(v) for v in box)

        hsv = cv2.cvtColor(frame_copy, cv2.COLOR_BGR2HSV)
        
        lower_red = (0, 100, 100)
        upper_red = (10, 255, 255)
        mask1 = cv2.inRange(hsv, lower_red, upper_red)
        lower_red = (170, 100, 100)
        upper_red = (180, 255, 255)
        mask2 = cv2.inRange(hsv, lower_red, upper_red)
        mask = mask1 + mask2
        
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if stump_box:
            sx, sy, sw, sh = stump_box
            cv2.rectangle(frame_copy, (sx, sy), (sx + sw, sy + sh), (255, 0, 0), 2)

        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) > 30:
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    ball_positions.append((center_x, center_y))
                    cv2.circle(frame_copy, (center_x, center_y), 5, (0, 255, 0), -1)

        if not prediction_made and len(ball_positions) > 5:
            dxs = [ball_positions[i][0] - ball_positions[i-1][0] for i in range(-4, 0)]
            dys = [ball_positions[i][1] - ball_positions[i-1][1] for i in range(-4, 0)]
            avg_dx = sum(dxs) / len(dxs) if dxs else 0
            avg_dy = sum(dys) / len(dys) if dys else 0

            if abs(avg_dx) > 0.1 or abs(avg_dy) > 0.1:
                last_pos = ball_positions[-1]
                end_x = int(last_pos[0] + avg_dx * 100)
                end_y = int(last_pos[1] + avg_dy * 100)
                
                # cv2.clipLine checks if a line segment intersects a rectangle.
                rect = (stump_box[0], stump_box[1], stump_box[0] + stump_box[2], stump_box[1] + stump_box[3])
                intersects = cv2.clipLine(rect, last_pos, (end_x, end_y))[0]
                
                if intersects:
                    final_decision = "out"
                    prediction_made = True

        if len(ball_positions) > 5: # Draw trajectory line after enough points are gathered
            last_pos = ball_positions[-1]
            # Use the same calculated velocity to draw the line
            end_x = int(last_pos[0] + avg_dx * 100)
            end_y = int(last_pos[1] + avg_dy * 100)
            cv2.line(frame_copy, last_pos, (end_x, end_y), (0, 255, 255), 2)
        
        if prediction_made and final_decision == "out":
            sx, sy, sw, sh = stump_box
            cv2.rectangle(frame_copy, (sx, sy), (sx + sw, sy + sh), (0, 0, 255), 3)
        
        frame_rgb = cv2.cvtColor(frame_copy, cv2.COLOR_BGR2RGB)
        
        try:
            frame_queue.put(frame_rgb, block=False)
        except queue.Full:
            continue
        
        time.sleep(delay)

    if is_auto_detecting:
        try:
            frame_queue.put(final_decision, timeout=1)
        except queue.Full:
            pass

def update_canvas_from_queue():
    """Checks queue for new frames and updates the canvas."""
    if not is_auto_detecting:
        return
    
    try:
        item = frame_queue.get_nowait()
        if isinstance(item, str):
            if item == "out": out()
            elif item == "not_out": not_out()
        else:
            photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(item))
            canvas.image = photo
            canvas.create_image(0, 0, image=photo, anchor=tkinter.NW)
    except queue.Empty:
        pass
    
    window.after(15, update_canvas_from_queue)

def start_auto_detection():
    global is_auto_detecting, detection_thread
    if not is_auto_detecting:
        is_auto_detecting = True
        detection_thread = threading.Thread(target=auto_detect_out_logic)
        detection_thread.daemon = True
        detection_thread.start()
        update_canvas_from_queue()

# --- GUI Setup ---
SET_WIDTH = 650
SET_HEIGHT = 368
window = tkinter.Tk()
window.title("Third Umpire Decision Review System")
window.configure(bg="#f0f0f0")

main_frame = tkinter.Frame(window, bg="#f0f0f0")
main_frame.pack(fill=tkinter.BOTH, expand=True, padx=10, pady=10)

right_frame = tkinter.Frame(main_frame, bg="#333")
right_frame.pack(side=tkinter.RIGHT, padx=(10, 0), pady=10)

left_frame = tkinter.Frame(main_frame, bg="#f0f0f0")
left_frame.pack(side=tkinter.LEFT, fill=tkinter.Y, padx=(0, 10), pady=10)

welcome_img_path = os.path.join(ASSETS_PATH, "dhoni.png")
cv_img = cv2.imread(welcome_img_path)
cv_img = imutils.resize(cv_img, width=SET_WIDTH, height=SET_HEIGHT)
cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
canvas = tkinter.Canvas(right_frame, width=SET_WIDTH, height=SET_HEIGHT, highlightthickness=0)
photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(cv_img))
image_on_canvas = canvas.create_image(0, 0, anchor=tkinter.NW, image=photo)
canvas.pack()

# --- Control Buttons ---
btn_font = ("Helvetica", 10, "bold")
btn_width = 20
btn_height = 2
uniform_pady = 8

btn_next = tkinter.Button(left_frame, text="Next (slow) >", width=btn_width, height=btn_height, font=btn_font, command=partial(play, 2), bg="#76c7c0", fg="white", relief="ridge")
btn_prev = tkinter.Button(left_frame, text="< Previous (slow)", width=btn_width, height=btn_height, font=btn_font, command=partial(play, -2), bg="#ff9f9f", fg="white", relief="ridge")
btn_next_fast = tkinter.Button(left_frame, text="Next (fast) >>", width=btn_width, height=btn_height, font=btn_font, command=partial(play, 25), bg="#48a9a6", fg="white", relief="ridge")
btn_prev_fast = tkinter.Button(left_frame, text="<< Previous (fast)", width=btn_width, height=btn_height, font=btn_font, command=partial(play, -25), bg="#ff6b6b", fg="white", relief="ridge")
btn_change_angle = tkinter.Button(left_frame, text="Change Angle", width=btn_width, height=btn_height, font=btn_font, command=cycle_angle, bg="#feca57", fg="white", relief="ridge")
btn_auto_detect_impact = tkinter.Button(left_frame, text="Auto-Detect Impact", width=btn_width, height=btn_height, font=btn_font, command=select_stumps, bg="#8e44ad", fg="white", relief="ridge")
btn_out = tkinter.Button(left_frame, text="Give Out", width=btn_width, height=btn_height, font=btn_font, command=out, bg="#d63031", fg="white", relief="ridge")
btn_not_out = tkinter.Button(left_frame, text="Give Not Out", width=btn_width, height=btn_height, font=btn_font, command=not_out, bg="#27ae60", fg="white", relief="ridge")

# Pack buttons with uniform spacing
btn_next.pack(pady=uniform_pady)
btn_prev.pack(pady=uniform_pady)
btn_next_fast.pack(pady=uniform_pady)
btn_prev_fast.pack(pady=uniform_pady)
btn_change_angle.pack(pady=uniform_pady)
btn_auto_detect_impact.pack(pady=uniform_pady)
btn_out.pack(pady=uniform_pady)
btn_not_out.pack(pady=uniform_pady)

window.mainloop()

