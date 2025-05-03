import tkinter as tk
import random

from .surface_model import MCUSurfaceModel

C_BG_MEDIUM = "#202020"
C_BG_DARK = "#001219"
C_BG_LIGHT = "#303030"
C_TRIM = "#005F73"
C_BUTTON_ON = "#EE9B00"
C_FADER = "#0A9396"
C_METER = "#67B99A"
C_TEXT_LIGHT = "#E9D8A6"
C_TEXT_DARK = C_BG_MEDIUM

BLACK = "#32292F"
BLUE = "#7798AB"
GREEN = "#002400"
RED = "#C20114"
YELLOW = "#ECA400"

UI_WIDTH = 1200
UI_HEIGHT = 675

class MCUSimulatorGUI:
    def __init__(self, master, surface: MCUSurfaceModel) -> None:
        self.master = master
        self.surface = surface
        self.canvas = tk.Canvas(master, width=UI_WIDTH, height=UI_HEIGHT, background=C_BG_MEDIUM)
        self.draw_surface()
        self.canvas.pack()
    
    def draw_surface(self) -> None:
        for i in range(len(self.surface.faders)):
            self.draw_channel(i)
        
        self.draw_master_section()
    

    def draw_master_section(self) -> None:
        x = 810
        y = 100
        x_width = 70

        self.canvas.create_rectangle(x, y, x + x_width, 600, fill=C_BG_LIGHT, outline=C_TRIM)

        # Fader
        fader_value = 50
        fader_x_offset = 25
        fader_y_anchor = 600
        fader_y = fader_y_anchor - (fader_value / 127) * 200
        self.canvas.create_rectangle(
            x+fader_x_offset+8,
            fader_y_anchor - 150,
            x+fader_x_offset+12,
            fader_y_anchor,
            fill=C_BG_DARK,
            outline=C_TRIM,
        )
        self.canvas.create_rectangle(
            x+fader_x_offset,
            fader_y,
            x+fader_x_offset+20,
            fader_y - 40,
            fill=C_FADER,
            outline=C_TRIM
        )
        self.canvas.create_text(
            x + fader_x_offset + 10,
            fader_y_anchor + 20,
            text=f"{fader_value}",
            fill=C_TEXT_LIGHT,
            font=("Helvetica", 16)
        )

        # Flip & Global buttons
        BUTTON_H = 30
        BUTTON_W = 30
        button_y_anchor = 400
        for b_i, b in enumerate(["FLIP", "GLOBAL\nVIEW"]):
            button_x = x + (BUTTON_W * b_i + 5 * b_i)
            button_y = button_y_anchor + 5 
            self.canvas.create_rectangle(button_x, button_y, button_x + BUTTON_W, button_y + BUTTON_H, fill=C_BUTTON_ON, outline=C_TRIM)
            self.canvas.create_text(button_x + BUTTON_W / 2, button_y + BUTTON_H / 2, text=b, fill=C_TEXT_DARK, font=("Helvetica", 12))
        



    def draw_channel(self, i: int) -> None:
        y = 100
        x = 10 + i * 100
        x_width = 70

        # Fader
        fader_value = i * 10
        fader_x_offset = 5
        fader_y_anchor = 600
        fader_y = fader_y_anchor - (fader_value / 127) * 200
        self.canvas.create_rectangle(
            x+fader_x_offset+8,
            fader_y_anchor - 150,
            x+fader_x_offset+12,
            fader_y_anchor,
            fill=C_BG_DARK,
            outline=C_TRIM,
        )
        self.canvas.create_rectangle(
            x+fader_x_offset,
            fader_y,
            x+fader_x_offset+20,
            fader_y - 40,
            fill=C_FADER,
            outline=C_TRIM
        )
        self.canvas.create_text(
            x + fader_x_offset + 10,
            fader_y_anchor + 20,
            text=f"{fader_value}",
            fill=C_TEXT_LIGHT,
            font=("Helvetica", 16)
        )

        # Meter (next to fader)
        meter_x = x + 40
        meter_y = fader_y_anchor - 150
        meter_height = 150
        meter_width = 25
        meter_value = random.uniform(0, 1)  # Simulate a meter value
        self.canvas.create_rectangle(
            meter_x,
            meter_y,
            meter_x + meter_width,
            meter_y + meter_height,
            fill=C_BG_DARK,
            outline=C_TRIM
        )
        self.canvas.create_rectangle(
            meter_x,
            meter_y + (1 - meter_value) * meter_height,
            meter_x + meter_width,
            meter_y + meter_height,
            fill=C_METER,
            outline=C_TRIM
        )
        self.canvas.create_text(
            meter_x + 15,
            fader_y_anchor + 20,
            text=f"{meter_value:.2f}",
            fill=C_TEXT_LIGHT,
            font=("Helvetica", 16)
        )

        # Buttons
        BUTTON_H = 30
        BUTTON_W = 60
        button_y_anchor = 300
        for b_i, b in enumerate(["REC", "SEL", "SOLO", "MUTE"]):
            button_x = x + 5
            button_y = button_y_anchor + 5 + (BUTTON_H * b_i + 5 * b_i)
            self.canvas.create_rectangle(button_x, button_y, button_x + BUTTON_W, button_y + BUTTON_H, fill=C_BUTTON_ON, outline=C_TRIM)
            self.canvas.create_text(button_x + BUTTON_W / 2, button_y + BUTTON_H / 2, text=b, fill=C_TEXT_DARK, font=("Helvetica", 16))
        
        # VPot Arc
        vpot_y_anchor = 235
        vpot_x = x + 5
        vpot_radius = 30
        vpot_value = 127
        vpot_angle = (vpot_value / 127) * 270
        self.canvas.create_arc(
            vpot_x,
            vpot_y_anchor,
            vpot_x + vpot_radius * 2,
            vpot_y_anchor + vpot_radius * 2,
            start=-135,
            extent=-vpot_angle,
            outline=C_BG_LIGHT,
            style=tk.ARC,
            width=10
        )
        self.canvas.create_text(vpot_x + vpot_radius, vpot_y_anchor + vpot_radius, text=f"{vpot_value}", fill=C_TEXT_LIGHT, font=("Helvetica", 16))

        # LCD
        lcd_x = x 
        lcd_y = 175
        lcd_width = x_width
        lcd_height = 40
        lcd_text = f"Channel {i}"
        self.canvas.create_rectangle(lcd_x, lcd_y, lcd_x + lcd_width, lcd_y + lcd_height, fill=C_BG_DARK, outline=C_TRIM)
        self.canvas.create_text(lcd_x + lcd_width / 2, lcd_y + lcd_height / 2, text=lcd_text, fill=C_TEXT_LIGHT, font=("Helvetica", 12))

    
    def update(self) -> None:
        self.canvas.delete("all")
        self.draw_surface()
        self.master.after(100, self.update)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("MCU Simulator")
    root.attributes("-topmost", True)
    root.geometry(f"{UI_WIDTH}x{UI_HEIGHT}")
    
    surface = MCUSurfaceModel()
    simulator = MCUSimulatorGUI(root, surface)
    
    simulator.update()
    root.mainloop()