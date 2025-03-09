
import numpy as np

    
def log_range(start,stop,pts_per_decade,endpoint=True):
    a = np.log10(float(start))
    b = np.log10(float(stop))
    pts_per_decade = int(pts_per_decade)
    if endpoint:
        x = 10**np.arange(a,b,1.0/pts_per_decade)        
        return(  np.append(x,stop) )
    else:
        return( 10**np.arange(a,b,1.0/pts_per_decade) )


def numberlist_string(s,numpy=True):
    '''
    converts a string of items seperated by ';' to a floating point list.
    each 'item' can be a scalar number or a range spec:
    <start>:<stop>:<step> (like 0:10:0.5)   
    or a  log pattern:    
    <start>::<stop>::<steps per decade> (like 1e-3::20::5) 
    (if steps are negative, the sequence is reversed)   
    or a repeat pattern:   
    <val1>#<val2>#<nr repeats> (0#1#3   -> 0,1,0,1,0,1)  
    ... as in the good ole labview days 😀
    '''
    l1 = s.split(';')
    l2 = []
    for s in l1:
        if '::' in s:
            l = s.split(':')
            l = [s for s in l if s != '']
            if len(l) != 3 : raise Exception('syntax error in ramp spec')
            if int(l[2]) <  0 :           
                x = log_range(l[0],l[1],abs(int(l[2])))
                x = x[::-1]
            else :
                x = log_range(l[0],l[1],l[2])
            l2 = l2 + list(x)                        
        elif ':' in s :
            l = s.split(':')
            if len(l) != 3 : raise Exception('syntax error in ramp spec')
            x = np.arange( float(l[0]),float(l[1]),float(l[2]) )             
            l2 = l2 + list(x) + [float(l[1])]
        elif '#' in s :
            l = s.split('#')
            if len(l) != 3 : raise Exception('syntax error in repeat (#) spec')
            l2 = l2 + [float(l[0]),float(l[1])] * int(l[2])
        elif s == '' :
            pass
        else:        
            l2.append(float(s))
    if numpy : return np.array(l2)
    else : return [float(x) for x in  l2]
