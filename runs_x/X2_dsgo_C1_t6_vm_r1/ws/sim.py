import re

def parse(path):
    prog=[]
    for raw in open(path):
        line=raw.split(';')[0].strip()
        if not line:
            continue
        parts=line.split()
        prog.append(parts)
    return prog

prog=parse('/tmp/<path>')
print("instructions:",len(prog))
for i,p in enumerate(prog): print(i,p)

regs={'a':0,'b':0,'c':0,'d':0}
def val(x):
    return regs[x] if x in regs else int(x)

def w(v): return v%65536

ip=0; out=[]; count=0
steps=0
while 0<=ip<len(prog):
    p=prog[ip]; op=p[0]; count+=1; steps+=1
    if steps>100000000:
        print("too many"); break
    if op=='set':
        regs[p[1]]=w(val(p[2])); ip+=1
    elif op=='add':
        regs[p[1]]=w(regs[p[1]]+val(p[2])); ip+=1
    elif op=='mul':
        regs[p[1]]=w(regs[p[1]]*val(p[2])); ip+=1
    elif op=='mod':
        x=val(p[2])
        if x>0: regs[p[1]]=regs[p[1]]%x
        ip+=1
    elif op=='dec':
        regs[p[1]]=max(0,regs[p[1]]-1); ip+=1
    elif op=='jnz':
        if val(p[1])!=0:
            ip+=val(p[2])
        else:
            ip+=1
    elif op=='skp':
        if val(p[1])<val(p[2]): ip+=2
        else: ip+=1
    elif op=='out':
        out.append(val(p[1])); ip+=1
    else:
        raise Exception(op)
    if count%1000000==0:
        pass
print("outputs count",len(out))
print("sum",sum(out))
print("executed",count)
print("first20",out[:20])
print("last20",out[-20:])
print("regs",regs)
