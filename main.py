import asyncio
import pygame


class AsyncRigControlServer:
    def __init__(self, primary_ip, primary_port):
        # Initialize server with IP addresses and ports for the primary radio
        self.primary_ip = primary_ip
        self.primary_port = primary_port
        self.running = False  # Flag to control the server's running state
        self.last_frequency = None  # Store the last read frequency for comparison
        self.frequency_step = 1000  # Frequency step for D-pad buttons (1 kHz)

        # Initialize pygame and joystick
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Using joystick: {self.joystick.get_name()}")
        else:
            print("No joystick detected!")

    async def open_connection(self):
        """Open TCP connection to the primary radio."""
        self.primary_reader, self.primary_writer = await asyncio.open_connection(self.primary_ip, self.primary_port)
        print(f"Connected to primary radio at {self.primary_ip}:{self.primary_port}")

    async def close_connection(self):
        """Close TCP connection to the primary radio."""
        self.primary_writer.close()
        await self.primary_writer.wait_closed()
        print("Closed connection to primary radio.")

    async def get_rig_data(self, command, reader, writer):
        """Send a command to a rig and receive the response."""
        writer.write(command.encode('utf-8'))
        await writer.drain()
        response = await reader.read(1024)
        response = response.decode('utf-8').strip()

        # Extract numeric part from the response (assuming it's the last line)
        frequency_str = response.split('\n')[-1].strip()  # Take the last line after splitting by newline
        print(f"Received response: {response}")

        # Try to convert to integer, if possible
        try:
            frequency = int(frequency_str)
            return frequency
        except ValueError:
            print(f"Error: Unable to convert response to integer: {frequency_str}")
            return None

    async def read_frequency(self):
        """Read frequency from the primary radio using the correct command."""
        return await self.get_rig_data('f\n', self.primary_reader, self.primary_writer)

    async def set_frequency(self, frequency):
        """Set frequency on the primary radio."""
        command = f'F {frequency}\n'
        self.primary_writer.write(command.encode('utf-8'))
        await self.primary_writer.drain()
        print(f"Set frequency to: {frequency}")

    async def handle_controller_input(self):
        """Handle D-pad input for shifting frequency and changing step size."""
        frequency_steps = [1000, 12500, 1000000]  # 1kHz, 12.5kHz, 1MHz
        step_index = 0  # Start with 1kHz as the default frequency step

        while self.running:
            pygame.event.pump()  # Process pygame events

            if self.joystick:
                # Get the state of the D-pad buttons (usually 0 = left, 1 = right)
                dpad_left = self.joystick.get_hat(0)[0] == -1  # D-pad left (left is -1)
                dpad_right = self.joystick.get_hat(0)[0] == 1  # D-pad right (right is 1)
                dpad_up = self.joystick.get_hat(0)[1] == 1  # D-pad up (up is 1)
                dpad_down = self.joystick.get_hat(0)[1] == -1  # D-pad down (down is -1)

                if dpad_left:
                    print("D-pad Left pressed, shifting frequency down")
                    if self.last_frequency is None:
                        self.last_frequency = 1000000  # Default starting frequency (1 MHz)
                    self.last_frequency = int(self.last_frequency) - frequency_steps[step_index]
                    await self.set_frequency(self.last_frequency)

                elif dpad_right:
                    print("D-pad Right pressed, shifting frequency up")
                    if self.last_frequency is None:
                        self.last_frequency = 1000000  # Default starting frequency (1 MHz)
                    self.last_frequency = int(self.last_frequency) + frequency_steps[step_index]
                    await self.set_frequency(self.last_frequency)

                elif dpad_up:
                    print("D-pad Up pressed, changing frequency step size")
                    step_index = (step_index + 1) % len(frequency_steps)  # Cycle to the next step size
                    print(f"Frequency step size changed to {frequency_steps[step_index] / 1000} kHz")

                elif dpad_down:
                    print("D-pad Down pressed, changing frequency step size")
                    step_index = (step_index - 1) % len(frequency_steps)  # Cycle to the previous step size
                    print(f"Frequency step size changed to {frequency_steps[step_index] / 1000} kHz")

            await asyncio.sleep(0.1)  # Poll every 100ms for input

    async def sync_frequencies(self):
        """Continuously read and print the frequency from the primary radio."""
        while self.running:
            freq = await self.read_frequency()
            if freq and freq != self.last_frequency:
                print(f"Frequency changed: {self.last_frequency} -> {freq}")
                self.last_frequency = freq
            await asyncio.sleep(0.1)  # Adjust the sync interval as needed

    async def start(self):
        """Start the rig control server."""
        await self.open_connection()
        self.running = True
        await asyncio.gather(self.sync_frequencies(), self.handle_controller_input())

    async def stop(self):
        """Stop the rig control server."""
        self.running = False
        await self.close_connection()


if __name__ == '__main__':
    # Configuration for the primary radio
    primary_ip = 'localhost'  # Replace with your primary radio's IP address
    primary_port = 4532  # Port for the primary radio

    server = AsyncRigControlServer(primary_ip, primary_port)
    try:
        # Run the server
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("Stopping Rig Control Server.")
        # Ensure server is properly stopped
        asyncio.run(server.stop())
