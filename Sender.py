import sys
import getopt
import time
import random
import pdb
import select

import Checksum
import BasicSender

'''
This is a skeleton sender class. Create a fantastic transport protocol here.
'''
class Sender(BasicSender.BasicSender):
    def __init__(self, dest, port, filename, debug=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        self.max_data_size = 1372
        self.windowsize = 5
        self.timeout = 0.5
        self.seqno = 0
        self.wnd = []

    # Main sending loop.
    def start(self):
        """ Send a file or get input from stdin. Send all data
        in order, reliably to receiver. """
        self.handle_file(self.infile) if filename else self.handle_stdin()
        # end_transmission = False
        # while not end_transmission:
        #     end_transmission = self.handle_file(self.infile) if filename else self.handle_stdin()
        #     # end_transmission = self.handle_file(open(self.filename)) \
        #     # if filename and self.infile else self.handle_stdin()
                  
    def handle_file(self, infile):
        """ To send data from file included with -f flag in sysargs.
        If data is piped from stdin, this function is called once
        it is determined stdin is nonempty. """

        # Initialize variables
        windowsize = self.windowsize

        # Initialize the generators that will yield the packets...
        segments = self.segment_data(infile, self.max_data_size)
        packets = self.get_packets(segments)

        # To keep track of which packets get acked
        acked = {}
        for i in range(self.seqno, self.seqno + len(self.wnd)):
            acked[i] = False

        # Attempt to establish a connection...
        start_packet = packets.next()
        self.initiate_connection(start_packet)
        acked[0] = True
        # Connection established!

        # Grab the first window of packets to send
        self.get_window(packets, windowsize)

        # Send the first window
        for packet in self.wnd:
            self.send(packet)

        # Main sending/receiving loop
        while True:

            # Wait to hear back from receiver. If receiver sends ack,
            # set appropriate flag in acked to True
            for packet in self.wnd:
                response = self.receive(self.timeout)

                # If we do get an ack, make sure it is not corrupted.
                if response and Checksum.validate_checksum(response):
                    ackno = int(self.split_packet(response)[1])

                    # This means a packet was dropped. Resend the window by exiting the response loop.
                    if ackno == self.seqno:
                        break

                    # Mark all packets up to acked packet as True
                    for j in range(0, ackno):
                        acked[j] = True

                    # Delete in order acked packets from the window
                    # to make room for more packets to fill the buffer
                    for i in range(self.seqno, ackno):
                        if acked[i]:
                            self.wnd.pop(0)
                            self.seqno += 1
                        else:
                            break
                else:
                    # Got a timeout for a packet, resend the window by exiting the response loop.
                    break

            # Refresh the window
            self.get_window(packets, windowsize)

            # If no packets left, we're done
            if not self.wnd:
                break

            # Send a new window
            for packet in self.wnd:
                self.send(packet)

        # Reset seqno and exit loop
        self.seqno = 0
        return True

    def handle_stdin(self):
        """ To send data that is input via stdin."""
        # This is stdin
        msg = self.infile
        # Check if stdin is empty, return 
        if not select.select([msg,],[],[],0.0)[0]:
            return True
        # Pass the buck to handle_file
        self.handle_file(msg)

    def initiate_connection(self, start_packet):
        """ Send a start packet and wait to hear back from
        receiver before sending more packets."""
        def conn_established(response):
            """ Helper. Checks if the ack packet is not 
            corrupted and that the seqno in the ack is 
            the next seqno."""
            return response and \
            Checksum.validate_checksum(response) and \
            int(self.split_packet(response)[1]) == self.seqno + 1

        # Loop until connection is established
        while self.seqno == 0:
            self.send(start_packet)
            response = self.receive(self.timeout)
            # Ensure the connection is properly established.
            if conn_established(response):
                self.seqno += 1

    def get_packets(self, segments, seqno=0):
        """ Yield the packets, in order with appropriate 
        flags for start, data, end. If all data fits in 
        start packet, there is no data packet."""
        msg_type = 'start'
        seg_buffer = [segments.next(), segments.next()]
        packet = self.make_packet(msg_type, seqno, seg_buffer.pop(0))
        yield packet
        seqno += 1
        if seg_buffer[0] is not '':
            seg_buffer.append(segments.next())
            msg_type = 'data'
            while seg_buffer[1] != '':
                packet = self.make_packet(msg_type, seqno, seg_buffer.pop(0))
                yield packet
                seg_buffer.append(segments.next())
                seqno += 1
        msg_type = 'end'
        packet = self.make_packet(msg_type, seqno, seg_buffer.pop(0))
        yield packet

    def segment_data(self, msg, seg_size):
        """ 
        To deal with data larger than the max packet size,
        we take in the original message, and return a 
        generator to yield segments of size seg_size.
        """
        segment = None
        while segment is not '':
            segment = bytes(msg.read(seg_size))
            yield segment

    def get_window(self, packets, wnd_size):
        """ Modify the sending window of self by adding
        packets until the sending buffer is full. Will not
        overwrite existing packets in the buffer. """
        while len(self.wnd) < wnd_size:
            try:
                self.wnd.append(packets.next())
            except StopIteration:
                break

    def handle_timeout(self):
        pass

    def handle_new_ack(self, ack):
        pass

    def handle_dup_ack(self, ack):
        pass

    def log(self, msg):
        if self.debug:
            print msg
 

'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print "BEARS-TP Sender"
        print "-f FILE | --file=FILE The file to transfer; if empty reads from STDIN"
        print "-p PORT | --port=PORT The destination port, defaults to 33122"
        print "-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost"
        print "-d | --debug Print debug messages"
        print "-h | --help Print this usage message"

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                               "f:p:a:d", ["file=", "port=", "address=", "debug="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False

    for o,a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True

    s = Sender(dest,port,filename,debug)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
