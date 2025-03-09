
import streamlit as st
from datetime import datetime
import plotly.express as px
import sk120
import time
from history import history
from numberlist import numberlist_string


app_info = '''
2025-02
developed with streamlit version 1.42
'''


print("page rerun")

st.set_page_config(
    'XY-SK120',
    layout='wide',
    page_icon='⚡',
    )

session = st.session_state
HISTORY_LEN =  5000 # total length of the history buffer in samples
MONITOR_PLOT_LENGTH = 250 #points shown in live plot
ditems = ('current A','voltage V','power W','Ah','Wh','T int','T ex', 'Vin')  # list of recordable items
modes = ("monitor","battery charge","IV curve","settings","memory config","history")
ALARMS = sk120.ALARM_FLAGS

if 'init' not in session: # init / config section
    session.init = True       
    session.modbusconfig = ('/dev/ttyUSB1', 1, 115200, 8)    
    session.time = 0    
    session.history = history(maxitems=HISTORY_LEN,columns=len(ditems))
    session.plotitem = ditems[0]
    session.period = 0.3
    session.plotpause = False
    session.pdef = '0:10:0.1'
    session.ctr = 0
    session.batteryloop = 0

#print(session)    

@st.cache_resource
def init():

    ser = sk120.Serial_modbus(*session.modbusconfig)
    dps = sk120.sk120(ser)	
    dps.status(True)    
    return dps

dps = init()

# the modes menu
mode = st.segmented_control("mode",
    modes,
    selection_mode="single",
    default='monitor',
    label_visibility='hidden',
    key='mode'
    )


def status_disp(vals,disable_ctrls=False):
        
    def onofftoggle(): dps.onoff_toggle()
    st.markdown(f"ON time: {vals['time']//60:02} : {vals['time']%60}:02")    
    cols = st.columns(6,border=True)
    cols[0].metric('Voltage',vals['voltage'])
    cols[1].metric('Current',vals['current'])
    cols[2].metric('Power',vals['power'])
    cols[3].metric('Ah',vals['ah'])
    cols[4].metric('Wh',vals['wh'])
    cols[5].metric('V in',vals['voltage_in'])

    c1,c2,c3,c4,c5,*_ = st.columns(6,vertical_alignment='top')
    c1.button('Output',key='onoff',on_click=onofftoggle,disabled=disable_ctrls)  #
    if vals['cc_cv'] > 0: s = "CC"
    else: s = 'CV'
    if vals['onoff'] :
        c2.markdown(f'### 🔴 {s}')  
    else:
        c2.markdown('### 🟢')  
            
    if c3.button(
        ALARMS[vals['status']][0],
        help = ALARMS[vals['status']][1] + ' - Press the button to clear alarm!',
        disabled = (vals['status']==0)
        ):
        dps.status(True)

    if c4.button('reset statistics',help='resets th Ah,Wh,time counters',disabled=disable_ctrls):
        dps.reset_statistics()            
        st.rerun()    
    if c5.button('disable protection',help='resets the over/under protection (OXX) settings',disabled=disable_ctrls):
        dps.remove_protection()          


def plot(plotitem=ditems[0],x_axis=0,sh = session.history,plotlen=MONITOR_PLOT_LENGTH):
    
    fig = px.line(x=None,y=None)
    
    fig.add_scatter(
        x = sh.head(plotlen)[x_axis], 
        y = sh.head(plotlen)[ditems.index(plotitem)+1].T,
        mode = 'lines',
        name = plotitem,
        line = dict(color="yellow")
        )
    labels = {'xaxis_title':"time in seconds",'yaxis_title':plotitem}    
    fig.update_layout(labels)
    st.plotly_chart(fig,use_container_width=True)  


def add_history(d):
    session.history.add(
            (
            d['current'],
            d['voltage'],
            d['power'],
            d['ah'],
            d['wh'],
            d['tint'],
            d['tex'],
            d['voltage_in']
            )
        )     



########################################################################################################
##############################                MODES                 ####################################
########################################################################################################  

if mode == modes[0]:######### monitor mode

    @st.fragment(run_every=session.period)
    def monitor_loop():                   
        
        t0 = time.time()
        
        def set_voltage():dps.sp_voltage(session.spvoltage)
        def set_current():dps.sp_current(session.spcurrent)
        
        d = dps.read_all()                   
        add_history(d)

        area1 = st.container()
        c1,c2,c3,c4,*_ = st.columns(6)
        c1.number_input('setpoint voltage',value=float(dps.sp_voltage()),format='%1.3f',key='spvoltage',on_change=set_voltage)
        c2.number_input('setpoint current',value=float(dps.sp_current()),format='%1.3f',key='spcurrent',on_change=set_current)
        c3.selectbox("item to plot",ditems,key="plotitem")                     

        session.ctr+=1    
    
        with area1:
            status_disp(d,disable_ctrls=False)           
            plot(session.plotitem)                            
    
        t1 = time.time()
        print(t1-t0,session.ctr)

    monitor_loop() # actually run the loop






if mode == modes[1]:############### battery mode
    
    print(session.batteryloop)
    def startloop():
        if session.batteryloop:        
            session.batteryloop = 0
        else : session.batteryloop = 1
        print('set ',session.batteryloop)

    @st.fragment(run_every=2.)
    def loop():  
        #session.batteryloop = 0
        d = dps.read_all()  
        status_disp(d)
        add_history(d)        
        i = st.selectbox('plot item',ditems)
        plot(i,plotlen=2000)
        if d['current'] <= session.jstop:
            dps.off()
            session.batteryloop = 0
            area0.info('charging completed! - check the history tab for the charging curve')
            time.sleep(5)
            st.rerun()
                
    presets = { #
        "LiIon 4.2V 18650":(4.2,2.,0.05,30.,90),
        "LiFePO 3.6V 18650":(3.6,2.,0.05,30.,90),
        "LiIon 12V":(12.6,2.,0.05,80.,90),
        "LiIon 20V 2Ah":(21.,2.,0.1,100.,90),
        "LiIon 20V 4Ah":(21.,4.,0.1,100.,90),
    }
    
    area0 = st.container()      
    p = st.selectbox('presets',presets.keys())
    p = presets[p]
    area1 = st.container()      
    with area1.form('iv',enter_to_submit=False):        
        col1,col2,col3,col4,col5,col6,*_ = st.columns(6)        
        col1.number_input('voltage limit',value=p[0],format="%1.3f",key='sp_v')
        col2.number_input('current limit',value=p[1],format="%1.3f",key='jmax')
        col3.number_input('low current stop',value=p[2],format="%1.3f",key='jstop')
        col4.number_input('power limit',value=p[3],key='pmax')
        col5.number_input('timer limit (min)',value=p[4],key='tmax')
        col6.checkbox('reset stats',True,key='resetstat')
        if session.batteryloop :
            stop = st.form_submit_button("stop charging",on_click=startloop)
        else :
            go = st.form_submit_button("start charging",on_click=startloop)

    if session.batteryloop:
        session.history.clear()
        dps.off()
        if session.resetstat : dps.reset_statistics()
        dps.sp_current(session.jmax)
        dps.sp_voltage(session.sp_v)
        dps.opp_mem(session.pmax)        
        dps.timer_mem(session.tmax)
        dps.on()  
        time.sleep(1)              
        loop()

    if not session.batteryloop :
        dps.off()
        dps.timer_mem(0)
            
    






if mode == modes[2]: ############## IV curve mode       
    

    def startloop():
        if session.batteryloop:        
            session.batteryloop = 0
        else : session.batteryloop = 1
        print('set ',session.batteryloop)

    @st.fragment(run_every=session.period)
    def loop(h):          
        d = dps.read_all()  
        status_disp(d)
        plot(plotitem=ditems[1],x_axis=1,sh=h)
                
    area1 = st.container()  

    if session.batteryloop :
        loop()
    

    for v in volts:
        dps.sp_voltage(v)
        time.sleep(session.waitms / 1000)
        d = dps.read_all()
        h.add(
            (
            d['sp_voltage'],
            d['current'],
            d['voltage'],
            d['power'],
            d['ah'],
            d['wh'],
            d['tint'],
            d['tex'],
            d['voltage_in']
            )
        )        
        

    with st.form('iv'):
        st.text_area('voltage parameter definition',value='0:1:0.1',key='pdef',help=numberlist_string.__doc__)
        col1,col2,col3,col4,*_ = st.columns(6)
        col1.number_input('wait time ms',value=1000,key='waitms',help='time to wait for the output to settle bevor reading the measurements')
        col2.checkbox('disable output',True,key='outdis')
        #col2.number_input('stop potential',value=0.0,key='vstop')
        col3.number_input('current limit',value=sk120.MAX_I,key='jmax')
        col4.number_input('power limit',value=sk120.MAX_P,key='pmax')
        go = st.form_submit_button("run IV")
    if go:
        try:
            volts = numberlist_string(session.pdef,numpy=False)
        except Exception as e:
            st.error('syntax error!')

        h = history(maxitems=len(volts)+1,columns=9)  
        dps.sp_current(session.jmax)
        dps.opp_mem(session.pmax)
        dps.sp_voltage(volts[0])
        dps.status(True)
        dps.on()

        disp = st.empty()
        with disp:
            for v in volts :
                d = dps.read_all()
                status_disp(d)
                time.sleep(session.waitms / 1000)
            
        if session.outdis : dps.off()
        
        temp = ("time_s", "sp_voltage") + ditems            
        csv = h.csv(headeritems=temp)                
    try:
        fname = f'{datetime.now():%Y-%m-%d_%H :%M:%S}_iv.csv'
        st.download_button('download csv file',data=csv,file_name=fname)  
    except NameError: pass # happens once on a fresh start

    

if mode == modes[3]: ############## settings mode   
    help_01 = "set to 0 to disable this protection/alarm" 
    def cb1() :dps.beeper(not dps.beeper())
    st.toggle('beeper',dps.beeper(),on_change=cb1)
    def cb2() :dps.lock(not dps.lock())
    st.toggle('lock',dps.lock(),on_change=cb2)
    t = st.number_input('timer in seconds',value=dps.timer_mem())
    dps.timer_mem(t)
    t = st.number_input('input low voltage protection (V)',min_value=5.5,value=dps.lvp_mem())
    dps.lvp_mem(t)
    t = st.number_input('input over voltage protection (V)',value=dps.ovp_mem())
    dps.ovp_mem(t)
    t = st.number_input('output over current protection (A)',min_value=0.,value=float(dps.ocp_mem()))
    dps.ocp_mem(t)
    t = st.number_input('output over power protection (W)',min_value=0.,value=float(dps.opp_mem()))
    dps.opp_mem(t)
    t = st.number_input('internal over temperatur protection',value=dps.otp_in_mem(),help=help_01)
    dps.otp_in_mem(t)
    t = st.number_input('external over temperatur protection',value=dps.otp_ex_mem(),help=help_01)
    dps.otp_ex_mem(t)
    t = st.number_input('max energy protection (Ah)',value=float(dps.oah_mem()),help=help_01)
    dps.oah_mem(t)
    t = st.number_input('max energy protection (Wh)',value=float(dps.owh_mem()),help=help_01)
    dps.owh_mem(t)
    
    

if mode == modes[4]:############# preset config
    d = dps.parameter_dict()
    st.markdown(f"### preset: {d['EXTRACT-M']}")
    st.markdown(f"### model: {d['MODEL']}, firmware: {d['VERSION']}")
    st.write(d)


if mode == modes[5]:############# history       
    sh = session.history
    st.selectbox(f"item to plot (records: {session.history.items})",ditems,key="plotitem")    
    c1,c2,c3,*_ = st.columns(6)
    temp = ("time_s",) + ditems            
    csv = session.history.csv(headeritems=temp)            
    fname = f'{datetime.now():%Y-%m-%d_%H :%M:%S}_history.csv'
    c1.download_button('download csv file',data=csv,file_name=fname)  
    if c2.button('clear history'):
        session.history.clear()
    c3.number_input('max records',value=session.history.maxitems,key='hmaxitems')
    
 
    fig = px.line(x=None,y=None)        
    fig.add_scatter(
        x = sh.mem[0][0:sh.items-1], 
        y = sh.mem[ditems.index(session.plotitem)+1][0:sh.items-1].T,
        mode = 'lines+markers',
        name = session.plotitem,
        line = dict(color="yellow")
        )
    labels = {'xaxis_title':"time in seconds",'yaxis_title':session.plotitem}    
    fig.update_layout(labels)
    st.plotly_chart(fig,use_container_width=True,)  
