"""
Enhanced 3D Model Controller with Arduino Joystick
===================================================
A PyGame/OpenGL application that renders a 3D model (e.g., Goku) and controls
its position and rotation using an Arduino joystick with real-time serial communication.

Features:
- Hardware-accelerated 3D rendering with proper lighting
- Arduino joystick integration for interactive control
- Smooth model transformations and camera management
- Comprehensive error handling and graceful degradation
"""

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import OpenGL.GL as gl
import OpenGL.GLU as glu
import pyassimp
import serial
import time
import os
import sys

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Display settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "3D Model Controller"
FOV = 45  # Field of view in degrees
NEAR_CLIP = 0.1
FAR_CLIP = 50.0
BACKGROUND_COLOR = (0.1, 0.1, 0.15, 1.0)  # Dark blue-gray

# Camera settings
CAMERA_DISTANCE = -8  # Distance from origin (negative = behind)

# Serial communication settings
SERIAL_PORT = 'COM12'  # Update this for your system (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 38400
SERIAL_TIMEOUT = 1
SERIAL_INIT_DELAY = 2  # Seconds to wait for Arduino initialization

# Model settings
MODEL_PATH = "untitled.fbx"  # Update with actual model path
MODEL_SCALE = 0.01  # Adjust based on your model's size

# Joystick control settings
JOYSTICK_CENTER = 512  # ADC center value (0-1023 range)
JOYSTICK_MAX = 512.0
MOVEMENT_SPEED = 0.1  # Units per frame
ROTATION_SPEED = 2.0  # Degrees per frame
JUMP_HEIGHT = 0.2  # Units per button press

# Rendering settings
TARGET_FPS = 60
FRAME_DELAY = 1000 // TARGET_FPS  # Milliseconds


# ============================================================================
# OPENGL INITIALIZATION
# ============================================================================

def initialize_opengl(width, height):
    """
    Initialize OpenGL rendering context with proper settings for 3D visualization.
    
    Args:
        width: Window width in pixels
        height: Window height in pixels
    """
    # Set up perspective projection
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()
    aspect_ratio = width / height
    glu.gluPerspective(FOV, aspect_ratio, NEAR_CLIP, FAR_CLIP)
    
    # Set up model view matrix
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, CAMERA_DISTANCE)
    
    # Enable depth testing for proper 3D rendering
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_LEQUAL)
    
    # Enable smooth shading for better visual quality
    gl.glShadeModel(gl.GL_SMOOTH)
    
    # Configure lighting for better model visibility
    gl.glEnable(gl.GL_LIGHTING)
    gl.glEnable(gl.GL_LIGHT0)
    
    # Set up light properties
    light_ambient = [0.2, 0.2, 0.2, 1.0]  # Ambient light (soft overall illumination)
    light_diffuse = [0.8, 0.8, 0.8, 1.0]  # Diffuse light (main directional light)
    light_specular = [1.0, 1.0, 1.0, 1.0]  # Specular highlights
    light_position = [5.0, 5.0, 5.0, 0.0]  # Directional light from top-right
    
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, light_ambient)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, light_diffuse)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_SPECULAR, light_specular)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, light_position)
    
    # Enable color material for easier material management
    gl.glEnable(gl.GL_COLOR_MATERIAL)
    gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)
    
    # Set material properties
    gl.glMaterialfv(gl.GL_FRONT, gl.GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
    gl.glMaterialf(gl.GL_FRONT, gl.GL_SHININESS, 50.0)
    
    # Enable backface culling for better performance
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    
    # Set background color
    gl.glClearColor(*BACKGROUND_COLOR)
    
    # Enable antialiasing hints
    gl.glHint(gl.GL_PERSPECTIVE_CORRECTION_HINT, gl.GL_NICEST)
    gl.glHint(gl.GL_POLYGON_SMOOTH_HINT, gl.GL_NICEST)
    
    print("✓ OpenGL initialized successfully")


# ============================================================================
# MODEL LOADING AND RENDERING
# ============================================================================

def load_3d_model(filepath):
    """
    Load a 3D model from file using PyAssimp.
    
    Args:
        filepath: Path to the 3D model file (OBJ, FBX, etc.)
        
    Returns:
        PyAssimp scene object containing the loaded model
        
    Raises:
        SystemExit: If model cannot be loaded
    """
    # Verify file exists
    if not os.path.exists(filepath):
        print(f"✗ Error: Model file '{filepath}' not found.")
        print(f"  Current directory: {os.getcwd()}")
        sys.exit(1)
    
    # Attempt to load model
    try:
        print(f"Loading model from: {filepath}")
        scene = pyassimp.load(filepath)
        
        # Verify model has geometry
        if not scene.meshes:
            print("✗ Error: Model file contains no meshes.")
            sys.exit(1)
            
        mesh_count = len(scene.meshes)
        vertex_count = sum(len(mesh.vertices) for mesh in scene.meshes)
        print(f"✓ Model loaded: {mesh_count} mesh(es), {vertex_count} vertices")
        
        return scene
        
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        sys.exit(1)


def render_model(scene):
    """
    Render all meshes in the loaded 3D model.
    
    Args:
        scene: PyAssimp scene object containing model data
    """
    for mesh in scene.meshes:
        # Check if mesh has normal data for proper lighting
        has_normals = mesh.normals.size > 0
        
        if has_normals:
            gl.glEnable(gl.GL_NORMALIZE)  # Ensure normals stay unit length after scaling
        
        # Render mesh as triangles
        gl.glBegin(gl.GL_TRIANGLES)
        
        for i in range(len(mesh.vertices)):
            # Apply normal for lighting calculations
            if has_normals:
                gl.glNormal3fv(mesh.normals[i])
            
            # Set vertex position
            gl.glVertex3fv(mesh.vertices[i])
        
        gl.glEnd()


# ============================================================================
# SERIAL COMMUNICATION
# ============================================================================

def initialize_serial(port, baud_rate, timeout):
    """
    Initialize serial connection to Arduino.
    
    Args:
        port: Serial port name (e.g., 'COM3' or '/dev/ttyUSB0')
        baud_rate: Communication speed in bits per second
        timeout: Read timeout in seconds
        
    Returns:
        Serial object if successful, None otherwise
    """
    try:
        print(f"Connecting to Arduino on {port} at {baud_rate} baud...")
        ser = serial.Serial(port, baud_rate, timeout=timeout)
        time.sleep(SERIAL_INIT_DELAY)  # Allow Arduino to reset
        print("✓ Serial connection established")
        return ser
        
    except serial.SerialException as e:
        print(f"✗ Serial connection failed: {e}")
        print("  Continuing without joystick input...")
        return None


def read_joystick_data(ser):
    """
    Read and parse joystick data from Arduino.
    
    Expected format: "x_value,y_value,button_state\\n"
    - x_value, y_value: 0-1023 (ADC readings)
    - button_state: 0 (pressed) or 1 (not pressed)
    
    Args:
        ser: Serial object for Arduino communication
        
    Returns:
        Tuple of (x_axis, y_axis, button_pressed) or None if no valid data
    """
    if ser is None or ser.in_waiting == 0:
        return None
    
    try:
        # Read and decode serial data
        line = ser.readline().decode('utf-8').strip()
        
        if not line:
            return None
        
        # Parse comma-separated values
        x_axis, y_axis, button = map(int, line.split(','))
        
        # Validate ranges
        if not (0 <= x_axis <= 1023 and 0 <= y_axis <= 1023):
            return None
        
        # Button is LOW (0) when pressed due to pull-up resistor
        button_pressed = (button == 0)
        
        return (x_axis, y_axis, button_pressed)
        
    except (ValueError, serial.SerialException, UnicodeDecodeError):
        # Silently ignore malformed data
        return None


# ============================================================================
# GAME STATE MANAGEMENT
# ============================================================================

class ModelController:
    """
    Manages the state and transformations of the 3D model.
    """
    
    def __init__(self):
        """Initialize model position and rotation."""
        self.position = [0.0, 0.0, 0.0]  # x, y, z coordinates
        self.rotation = [0.0, 0.0, 0.0]  # Rotation around x, y, z axes (degrees)
        self.velocity = [0.0, 0.0, 0.0]  # For smooth movement
        
    def update_from_joystick(self, joystick_data):
        """
        Update model state based on joystick input.
        
        Args:
            joystick_data: Tuple of (x_axis, y_axis, button_pressed)
        """
        if joystick_data is None:
            return
        
        x_axis, y_axis, button_pressed = joystick_data
        
        # Normalize joystick values to -1.0 to 1.0 range
        x_normalized = (x_axis - JOYSTICK_CENTER) / JOYSTICK_MAX
        y_normalized = (y_axis - JOYSTICK_CENTER) / JOYSTICK_MAX
        
        # Apply deadzone to prevent drift (ignore small values near center)
        deadzone = 0.1
        if abs(x_normalized) < deadzone:
            x_normalized = 0.0
        if abs(y_normalized) < deadzone:
            y_normalized = 0.0
        
        # Update horizontal movement (left/right)
        self.position[0] += x_normalized * MOVEMENT_SPEED
        
        # Update rotation (around Y-axis)
        self.rotation[1] += y_normalized * ROTATION_SPEED
        
        # Keep rotation in 0-360 range for cleaner values
        self.rotation[1] %= 360
        
        # Handle jump button
        if button_pressed:
            self.position[1] += JUMP_HEIGHT
        else:
            # Apply gravity (simple implementation)
            if self.position[1] > 0.0:
                self.position[1] = max(0.0, self.position[1] - 0.05)
    
    def apply_transformations(self):
        """Apply position and rotation transformations to OpenGL matrix."""
        # Translate to position
        gl.glTranslatef(self.position[0], self.position[1], self.position[2])
        
        # Apply rotations
        gl.glRotatef(self.rotation[0], 1, 0, 0)  # Pitch (X-axis)
        gl.glRotatef(self.rotation[1], 0, 1, 0)  # Yaw (Y-axis)
        gl.glRotatef(self.rotation[2], 0, 0, 1)  # Roll (Z-axis)
        
        # Scale model to appropriate size
        gl.glScalef(MODEL_SCALE, MODEL_SCALE, MODEL_SCALE)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application loop."""
    
    # Initialize Pygame
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    display = (WINDOW_WIDTH, WINDOW_HEIGHT)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    
    # Initialize OpenGL
    initialize_opengl(WINDOW_WIDTH, WINDOW_HEIGHT)
    
    # Load 3D model
    scene = load_3d_model(MODEL_PATH)
    
    # Initialize serial communication
    serial_connection = initialize_serial(SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT)
    
    # Initialize model controller
    controller = ModelController()
    
    # Display controls
    print("\n" + "="*50)
    print("CONTROLS:")
    print("  Joystick X-axis: Move left/right")
    print("  Joystick Y-axis: Rotate model")
    print("  Button: Jump/Move up")
    print("  ESC or Close Window: Quit")
    print("="*50 + "\n")
    
    # Main game loop
    clock = pygame.time.Clock()
    running = True
    
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Read joystick input
        joystick_data = read_joystick_data(serial_connection)
        controller.update_from_joystick(joystick_data)
        
        # Clear buffers
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        # Render model with transformations
        gl.glPushMatrix()
        controller.apply_transformations()
        render_model(scene)
        gl.glPopMatrix()
        
        # Update display
        pygame.display.flip()
        clock.tick(TARGET_FPS)
    
    # Cleanup
    print("\nShutting down...")
    if scene:
        pyassimp.release(scene)
    if serial_connection:
        serial_connection.close()
    pygame.quit()
    print("✓ Cleanup complete")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)