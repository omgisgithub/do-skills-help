prog=[]
for raw in open('/tmp/<path>'):
    line=raw.split(';')[0].strip()
    if line: prog.append(line.split())
regs={'a':0,'b':0,'c':0,'d':0}
def val(x): return regs[x] if x in regs else int(x)
def w(v): return v%65536
ip=0; out=[]; total=0; iter_log=[]
while 0<=ip<len(prog):
    p=prog[ip]; total+=1; op=p[0]
    if op=='set': regs[p[1]]=w(val(p[2])); ip+=1
    elif op=='add': regs[p[1]]=w(regs[p[1]]+val(p[2])); ip+=1
    elif op=='mul': regs[p[1]]=w(regs[p[1]]*val(p[2])); ip+=1
    elif op=='mod':
        x=val(p[2])
        if x>0: regs[p[1]]=regs[p[1]]%x
        ip+=1
    elif op=='dec': regs[p[1]]=max(0,regs[p[1]]-1); ip+=1
    elif op=='jnz':
        k=val(p[2])
        if val(p[1])!=0: ip+=k
        else: ip+=1
    elif op=='skp':
        if val(p[1])<val(p[2]):
            iter_log.append((regs['a'],regs['b'],regs['c'],regs['d'],'skip'))
            ip+=2
        else:
            iter_log.append((regs['a'],regs['b'],regs['c'],regs['d'],'noskip'))
            ip+=1
    elif op=='out': out.append(val(p[1])); ip+=1
print("iterations",len(iter_log))
print("last 5:",iter_log[-5:])
print("skips",sum(1 for x in iter_log if x[4]=='skip'))
print("out len",len(out),"sum",sum(out),"count",total)
# verify c = sum of a mod 65536 before override
print("c",regs['c'], "sum a mod", sum(x[0] for x in iter_log)%65536)
