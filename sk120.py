import minimalmodbus
import time
import csv


'''
took code from https://github.com/lambcutlet/DPS5005_pyGUI
# original inspiration for this came from here:
# DPS3005 MODBUS Example By Luke (www.ls-homeprojects.co.uk) 
#
# Requires minimalmodbus library from: https://github.com/pyhys/minimalmodbus

Note:
The methods that end with '_mem' can change the values in one of the memory presets if the mem parameter [1-10] is given. 
Otherwise they change the current settings
'''		


MAX_V_IN = 36.
MAX_I = 6.
MAX_P = 120.


ALARM_FLAGS = ( # ordered by return values of the protect(function)
    ('','normal operation'),
    ('OVP','over voltage'),    
    ('OCP','over current'),
    ('OPP','over power'),
    ('LVP','input under voltage'),
    ('OAH','maximum time'),
    ('OHP','maximum output power'),
    ('OTP','maximum internal temperature'),
    ('OEP','no load'),
    ('OWH','maximum energy passed'),
    ('ICP','maximum input power'),
    ('ETO','maximum external temperature'),
)


def read_cmds(file = 'cmdlist.tsv'):
    'returns the cmd list as a dictionary from a tsv file, used by sk120'
    with open(file) as f:            
        cr = csv.DictReader(f,delimiter='\t')
        cr = list(cr)
        d = {}    
        for c in cr:   
            c['bytes'] = int(c['bytes'])
            c['dec'] = int(c['dec'])
            c['io'] = int(c['io'])
            c['reg'] = int(c['reg'],16)
            d[c['name']] = c    
        return d


class Serial_modbus:
    def __init__(self, port1, addr, baud_rate, byte_size ):
        self.instrument = minimalmodbus.Instrument(port1, addr) # port name, slave address (in decimal)
        #self.instrument.serial.port          # this is the serial port name
        self.instrument.serial.baudrate = baud_rate   # Baud rate 9600 as listed in doc
        self.instrument.serial.bytesize = byte_size
        self.instrument.serial.timeout = 0.5     # This had to be increased from the default setting else it did not work !
        self.instrument.mode = minimalmodbus.MODE_RTU  #RTU mode

    def read(self, reg_addr, decimal_places):
        return self.instrument.read_register(reg_addr, decimal_places)
        
    def read_block(self, reg_addr, size_of_block):
        return self.instrument.read_registers(reg_addr, size_of_block)
            
    def write(self, reg_addr, value, decimal_places):
        self.instrument.write_register(reg_addr, value, decimal_places) # register, value, No_of_decimal_places
    
    def write_block(self, reg_addr, value):
        self.instrument.write_registers(reg_addr, value)



class sk120:

    def __init__(self, ser):
        self.cmds = read_cmds()
        self.serial_data = ser	            
        
    def _read(self,cmd):        
        try:
            return self.serial_data.read(self.cmds[cmd]['reg'],self.cmds[cmd]['dec'])
        except IOError:
            print("Failed to read from instrument")        		
    
    def _read_blk(self,addr,len):        
        try:
            return self.serial_data.read_block(addr,len)
        except IOError:
            print("Failed to read from instrument")        		
    
    def _write(self,cmd,value):        
        try:            
            return self.serial_data.write(self.cmds[cmd]['reg'], value, self.cmds[cmd]['dec'])
        except IOError:
            print("Failed to write to instrument")        		
    
    def _write_mem(self,cmd,value,mem = None):
        '''this is writing to the memory presets M0-M9
        If mem is not provided, the current preset is queried from the device
        '''        
        if mem == None:
            mem = self.preset()
        try:            
            addr = self.cmds[cmd]['reg'] + mem * 0x10
            return self.serial_data.write(addr, value, self.cmds[cmd]['dec'])
        except IOError:
            print("Failed to write to instrument")        		

    def _write_blk_mem(self,cmd,blk,mem = None):
        'this is writing a bytes to the memory presets M0-M9'        
        if mem == None:
            mem = self.preset()
        try:            
            addr = self.cmds[cmd]['reg'] + mem * 0x10
            return self.serial_data.write_block(addr, list(blk))
        except IOError:
            print("Failed to write to instrument")        		

    def _read_mem(self,cmd,mem=None):
        '''this is reading from the memory presets M0-M9.
        If mem is not provided, the current preset is queried from the device
        '''                
        if mem == None:
            mem = self.preset()
        try:            
            addr = self.cmds[cmd]['reg'] + mem * 0x10
            return self.serial_data.read(addr, self.cmds[cmd]['dec'])
        except IOError:
            print("Failed to read from instrument")        		


    def sp_voltage(self,val = None):
        if val == None:
            return self._read('V-SET')
        else :
            return self._write('V-SET',val)
    
    def sp_current(self,val = None):
        if val == None:
            return self._read('I-SET')
        else :
            return self._write('I-SET',val)    

    def current(self):
        return self._read('IOUT')
    
    def voltage(self):
        return self._read('VOUT')

    def power(self):
        return self._read('POWER')        

    def voltage_in(self):	
        return self._read('UIN')

    def lock(self,state = None):
        if state == None:
            return self._read('LOCK')
        else :
            return self._write('LOCK',int(state))    
        
    def status(self,reset = False):	
        'alarm status , original: protect signal'
        ret = self._read('PROTECT')
        if reset : self._write('PROTECT',0)
        return ret
    def status_str(self):
        'returns a tuple: (abrv,long desc)'
        return ALARM_FLAGS[self.status()]

    def cv_cc(self):
        return self._read('CVCC')

    def onoff(self):
        return self._read('ONOFF') > 0
    def on(self):
        return self._write('ONOFF',1)
    def off(self):
        return self._write('ONOFF',0)
    def onoff_toggle(self):
        if self.onoff():
            self.off()
            return False
        else: 
            self.on()
            return True

    def time(self):
        'returns time as tuple,(total_seconds,h,m,s)'
        h = self._read('OUT_H')
        m = self._read('OUT_M')
        s = self._read('OUT_S')
        return s + 60*m + 3600*h, h,m,s

    def wh(self):
        'W x h energy output in Wh'
        l = self._read('WH-LOW')
        h = self._read('WH-HIGH')
        return (l + (h << 16)) / 1000.

    def ah(self):
        'A x h energy output in Ah'
        l = self._read('AH-LOW')
        h = self._read('AH-HIGH')        
        return (l + (h << 16)) / 1000.
    
    def read_all(self):
        'fast block reading of most values, returns a dict'
        data = self._read_blk(0x00,30) #~10ms @ 115200 baud
        d = {}
        d['sp_voltage'] = data[0] / 10**(self.cmds['V-SET']['dec'])
        d['sp_current'] = data[1] / 10**(self.cmds['I-SET']['dec'])
        d['voltage'] = data[2] / 10**(self.cmds['VOUT']['dec'])
        d['current'] = data[3] / 10**(self.cmds['IOUT']['dec'])
        d['power'] = data[4] / 10**(self.cmds['POWER']['dec'])
        d['voltage_in'] = data[5] / 10**(self.cmds['UIN']['dec'])
        ahl = data[6];ahh = data[7]
        d['ah'] = (ahl + (ahh << 16)) / 1000.
        whl = data[8];whh = data[9]
        d['wh'] = (whl + (whh << 16)) / 1000.
        th =  data[10];tm =  data[11];ts =  data[12]
        d['time'] = int(ts + 60*tm + 3600*th)
        d['tint'] = data[13] / 10**(self.cmds['T_IN']['dec'])
        d['tex'] = data[14] / 10**(self.cmds['T_EX']['dec'])
        d['status'] = data[16]
        d['cc_cv'] = data[17]
        d['onoff'] = data[18]
        d['FC'] = data[19]
        d['bled'] = data[20]
        d['sleep'] = data[21]
        d['model'] = data[22]
        d['firmware'] = data[23]
        d['addr'] = data[24]
        d['baud'] = data[25]
        d['preset'] = data[29]
        return d


    def preset(self,val = None):
        '''returns the active device preset channel
           sets the device preset,  0-9 
        '''
        if val == None:
            return self._read('EXTRACT-M')
        else :
            return self._write('EXTRACT-M',val)


    def reset_statistics(self):
        'resets the energy and time values'
        # different from the table, writing to this registers is possible and clears the data!        
        
        self._write('OUT_H',0) # seems to reset total time...      
        self._write('WH-LOW',0)
        self._write('WH-HIGH',0)
        self._write('AH-LOW',0)
        self._write('AH-HIGH',0)        

    def parameter_dict(self):
        'returns a dict of all active paramters and their values'
        d = {}
        for key in self.cmds.keys():
            v = self._read(key)
            d[key] = v
        return d
    
    def beeper(self,state = None):
        'beeper status, set bool or int'
        if state == None:
            return self._read('BUZZER')
        else :
            return self._write('BUZZER',int(state))

    def const_power(self,state = None):
        'switches on off the const power mode'
        if state == None:
            return self._read('CW-SW')
        else :
            return self._write('CW-SW',int(state))
    
    def const_power_val(self,val = None):
        'sets the value for the const power mode'
        if state == None:
            return self._read('CW')
        else :
            return self._write('CW',val)

    def bat_current_threshold(self,val = None):
        # does not work like this....
        'output goes off if the current falls below this value. Set to 0 to disable'
        if val == None:
            return self._read('BAT-FUL')
        else :
            return self._write('BAT-FUL',val)

    def sp_voltage_mem(self,val = None,mem = None):        
        if val == None:
            return self._read_mem('S-V-SET',mem)
        else :            
            return self._write_mem('S-V-SET',val,mem)

    def sp_current_mem(self,val = None,mem = None):
        if val == None:
            return self._read_mem('S-I-SET',mem)
        else :
            return self._write_mem('S-I-SET',val,mem)

    def timer_mem(self,val = None,mem = None):
        'sets the max time in minutes after the output will be switched off'
        if val == None:
            m = self._read_mem('S-OHP_M',mem)
            h = self._read_mem('S-OHP_H',mem)
            return m + h * 60
        else :
            m = val % 60       
            h = val // 60     
            self._write_mem('S-OHP_H',h,mem)
            return self._write_mem('S-OHP_M',m,mem)

    def lvp_mem(self,val = None,mem = None):
        'input low voltage protection'
        if val == None:
            return self._read_mem('S-LVP',mem)
        else :
            return self._write_mem('S-LVP',val)

    def ovp_mem(self,val = None,mem = None):
        'input over voltage protection'
        if val == None:
            return self._read_mem('S-OVP',mem)
        else :
            return self._write_mem('S-OVP',val,mem)
    
    def ocp_mem(self,val = None,mem = None):
        'output over current protection'
        if val == None:
            return self._read_mem('S-OCP',mem)
        else :
            return self._write_mem('S-OCP',val,mem)
    
    def opp_mem(self,val = None,mem = None):
        'output over power protection'
        if val == None:
            return self._read_mem('S-OPP',mem)
        else :
            return self._write_mem('S-OPP',val,mem)

    def otp_in_mem(self,val = None,mem = None):
        'internal over temperatur protection'
        if val == None:
            return self._read_mem('S-OTP',mem)
        else :
            return self._write_mem('S-OTP',val,mem)

    def otp_ex_mem(self,val = None,mem = None):
        'external over temperatur protection'
        if val == None:
            return self._read_mem('S-ETP',mem)
        else :
            return self._write_mem('S-ETP',val,mem)


    def oah_mem(self,val = None,mem = None):
        'sets the max energy in AH the output will be switched on, max 65Ah'
        if val == None:
            l = self._read_mem('S-OAH_L',mem)
            h = self._read_mem('S-OAH_H',mem)                    
            return (l + (h<<16)) / 1000 # in Ah
        else :
            val = int(val * 1000)            
            l = val & 0xFFFF
            h = (val >> 16)                          
            self._write_mem('S-OAH_H',h,mem) # there seems to be a bug: only the last operation is used (either L or H)
            self._write_mem('S-OAH_L',l,mem)
            return

    def owh_mem(self,val = None,mem = None):
        'sets the max energy in Wh the output will be switched on, Max 650Wh'        
        if val == None:
            l = self._read_mem('S-OWH_L',mem)
            h = self._read_mem('S-OWH_H',mem)            
            return (l + (h<<16)) / 100 # in Wh, why 100 here I dont know
        else :
            val = int(val * 100)            
            l = val & 0xFFFF
            h = (val >> 16)                 
            self._write_mem('S-OWH_H',h,mem) # # there seems to be a bug: only the last operation is used (either L or H)
            return self._write_mem('S-OWH_L',l,mem)

    def remove_protection(self):
        'resets all output protection settings to default/max. Internal OTP and input voltage are left untouched'        
        self.ovp_mem(MAX_V_IN)
        self.ocp_mem(MAX_I)
        self.opp_mem(MAX_P)
        self.oah_mem(0)
        self.owh_mem(0)
        self.otp_ex_mem(0)
        self.timer_mem(0)
        self.bat_current_threshold(0)

    

if __name__ == '__main__':

    ser = Serial_modbus('/dev/ttyUSB0', 1, 115200, 8)
    dps = sk120(ser)	
    
    #dps.on()
    print(dps.read_all())

    #print(dps._read('S-OTP'))
    #dps._write('B-LED',3)
    dps.beeper(0)
    
    print(dps.status(True))
    
    dps.off()
    
    print(dps.parameter_dict())
    