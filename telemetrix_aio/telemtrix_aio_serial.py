# -*- coding: utf-8 -*-
"""
 Copyright (c) 2015-2024 Alan Yorinks All rights reserved.

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
 Version 3 as published by the Free Software Foundation; either
 or (at your option) any later version.
 This library is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
 along with this library; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import asyncio
import sys
import serial
import time

LF = 0x0a


# noinspection PyStatementEffect,PyUnresolvedReferences,PyUnresolvedReferences
class TelemetrixAioSerial:
    """
    This class encapsulates management of the serial port that communicates
    with the Arduino Firmata
    It provides a 'futures' interface to make Pyserial compatible with asyncio
    """

    def __init__(self, com_port='/dev/ttyACM0', baud_rate=115200, sleep_tune=.0001,
                 telemetrix_aio_instance=None, close_loop_on_error=True):

        """
        This is the constructor for the aio serial handler

        :param com_port: Com port designator
        
        :param baud_rate: UART baud rate
        
        :param telemetrix_aio_instance: reference to caller
        
        :return: None
        """
        # print('Initializing Arduino - Please wait...', end=" ")
        sys.stdout.flush()
        self.my_serial = serial.Serial(com_port, baud_rate, timeout=1,
                                       writeTimeout=1)

        self.com_port = com_port
        self.sleep_tune = sleep_tune
        self.telemetrix_aio_instance = telemetrix_aio_instance
        self.close_loop_on_error = close_loop_on_error

        # used by read_until
        self.start_time = None

    async def get_serial(self):
        """
        This method returns a reference to the serial port in case the
        user wants to call pyserial methods directly

        :return: pyserial instance
        """
        return self.my_serial

    async def write(self, data):
        """
        This is an asyncio adapted version of pyserial write. It provides a
        non-blocking  write and returns the number of bytes written upon
        completion

        :param data: Data to be written
        :return: Number of bytes written
        """
        # the secret sauce - it is in your future
        future = asyncio.Future()
        result = None
        try:
            # result = self.my_serial.write(bytes([ord(data)]))
            result = self.my_serial.write(bytes(data))

        except serial.SerialException as e:
            # noinspection PyBroadException
            # loop = None
            await self.close()
            raise e
            future.cancel()
            if self.close_loop_on_error:
                loop = asyncio.get_event_loop()
                loop.stop()

            if self.telemetrix_aio_instance.the_task:
                self.telemetrix_aio_instance.the_task.cancel()
            await asyncio.sleep(1)
            if self.close_loop_on_error:
                loop.close()

        if result:
            future.set_result(result)
            while True:
                if not future.done():
                    # spin our asyncio wheels until future completes
                    await asyncio.sleep(self.sleep_tune)

                else:
                    return future.result()


    async def read(self, size=1):
        """
        Non-blocking read that also propagates SerialException.
        """
        while True:
            try:
                if not self.my_serial.in_waiting:
                    await asyncio.sleep(self.sleep_tune * 2)
                    continue

                data = self.my_serial.read(size)
                return ord(data) if size == 1 else list(data)

            except serial.SerialException as e:
                await self.close()
                raise e


    async def read_until(self, expected=LF, size=None, timeout=1):
        """
        Read until *expected* byte or timeout; propagates SerialException.
        """
        expected = str(expected).encode()
        start_time = time.time()

        while True:
            try:
                if not self.my_serial.in_waiting:
                    if timeout and (time.time() - start_time) > timeout:
                        return None
                    await asyncio.sleep(self.sleep_tune)
                    continue

                data = self.my_serial.read_until(expected, size)
                return list(data)

            except serial.SerialException as e:
                await self.close()
                raise e


    async def reset_input_buffer(self):
        """
        Reset the input buffer
        """
        self.my_serial.reset_input_buffer()

    async def close(self):
        """
        Close the serial port
        """
        if self.my_serial:
            self.my_serial.close()
