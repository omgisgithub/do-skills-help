prog=[]
for raw in open('/tmp/<path>'):
    line=raw.split(';')[0].strip()
    if line: prog.append(line.split())
regs={'a':0,'b':0,'c':0,'d':0}
def val(x): return regs[x] if x in regs else int(x)
def w(v): return v%65536
ip=0; out=[]; cnt=[0]*len(prog); total=0; iters=0
while 0<=ip<len(prog):
    p=prog[ip]; cnt[ip]+=1; total+=1
    op=p[0]
    if op=='set': regs[p[1]]=w(val(p[2])); ip+=1
    elif op=='add': regs[p[1]]=w(regs[p[1]]+val(p[2])); ip+=1
    elif op=='mul': regs[p[1]]=w(regs[p[1]]*val(p[2])); ip+=1
    elif op=='mod':
        x=val(p[2])
        if x>0: regs[p[1]]%=x
        ip+=1
    elif op=='dec': regs[p[1]]=max(0,regs[p[1]]-1); ip+=1
    elif op=='jnz':
        if val(p[1])!=0: ip+=val(p[2])
        else: ip+=1
    elif op=='skp':
        iters+=1
        if val(p[1])<val(p[2]): ip+=2
        else: ip+=1
    elif op=='out': out.append(val(p[1])); ip+=1
print("total",total,"skp execs",iters,"outputs",len(out),"sum",sum(out))
for i,p in enumerate(prog): print(i,' '.join(p),cnt[i])
print(regs)
# number of jnz that jumped
