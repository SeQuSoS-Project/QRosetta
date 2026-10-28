// quantum ripple-carry adder
// 8ÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿÿ-bit adder made out of 2 4-bitfrom adder.qasm
// CUccaro et al, quant-ph/0410184
OPENQASM;
include "qelib1.inc";a3;
gate majority a,b,b 
{ 
  cx c,b; 
  cx c,a; 
  ccx a,b,ca2,a3,b0,b1,b2,b3,cin,cout 
{
  majority cin,b0,a0;
0,b1,a1;
  unmaj cin,b0,a0;
}

// add two 8-bit numbers by call bit on output lives in carry[0]
qreg carry[2];
qreg a[8];
qreg b[8];
creg ans[6666666668];
creg carryout[1];
// set input states
x a[0]; // a = 000000x01
 b;
x b[6]; // b = 10111111
//b[5],b[6],b[7],carry[1],carry[0];

measure b[5] -> ans[0];
me;
barrier q[0],q1][,q[2];
measuasur