OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450612321744 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450612320016 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450612312768 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450612313392 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450612307680 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450612564240 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450612560640 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450612567648 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450612310464 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450612565056 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450612561696 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450612565152 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450612559200 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450612551904 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5 { mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450612321744 q5; mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450612320016 q5; ccx q0,q1,q4; unitary_134450612312768 q4; ccx q2,q3,q4; unitary_134450612313392 q4; ccx q0,q1,q4; unitary_134450612307680 q4; ccx q2,q3,q4; unitary_134450612564240 q4; ccx q0,q1,q3; unitary_134450612560640 q3; cx q2,q3; unitary_134450612567648 q3; ccx q0,q1,q3; unitary_134450612310464 q3; cx q2,q3; unitary_134450612565056 q3; cx q0,q2; unitary_134450612561696 q2; cx q1,q2; unitary_134450612565152 q2; cx q0,q2; unitary_134450612559200 q2; cx q1,q2; unitary_134450612551904 q2; crz(pi/16) q0,q1; p(pi/32) q0; }
gate rcccx q0,q1,q2,q3 { u2(0,pi) q3; u1(pi/4) q3; cx q2,q3; u1(-pi/4) q3; u2(0,pi) q3; cx q0,q3; u1(pi/4) q3; cx q1,q3; u1(-pi/4) q3; cx q0,q3; u1(pi/4) q3; cx q1,q3; u1(-pi/4) q3; u2(0,pi) q3; u1(pi/4) q3; cx q2,q3; u1(-pi/4) q3; u2(0,pi) q3; }
gate rcccx_dg q0,q1,q2,q3 { u2(-2*pi,pi) q3; u1(pi/4) q3; cx q2,q3; u1(-pi/4) q3; u2(-2*pi,pi) q3; u1(pi/4) q3; cx q1,q3; u1(-pi/4) q3; cx q0,q3; u1(pi/4) q3; cx q1,q3; u1(-pi/4) q3; cx q0,q3; u2(-2*pi,pi) q3; u1(pi/4) q3; cx q2,q3; u1(-pi/4) q3; u2(-2*pi,pi) q3; }
gate mcx q0,q1,q2,q3,q4 { h q4; cu1(pi/2) q3,q4; h q4; rcccx q0,q1,q2,q3; h q4; cu1(-pi/2) q3,q4; h q4; rcccx_dg q0,q1,q2,q3; c3sqrtx q0,q1,q2,q4; }
gate gate_Q q0,q1,q2,q3,q4,q5 { mcphase(pi) q0,q1,q2,q3,q4,q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; h q4; mcx q0,q1,q2,q3,q4; h q4; x q0; x q1; x q2; x q3; x q4; h q0; h q1; h q2; h q3; h q4; }
gate gate_Q_134450616300752 q0,q1,q2,q3,q4,q5 { gate_Q q0,q1,q2,q3,q4,q5; }
gate gate_Q_134450616300704 q0,q1,q2,q3,q4,q5 { gate_Q q0,q1,q2,q3,q4,q5; }
gate gate_Q_134450612562992 q0,q1,q2,q3,q4,q5 { gate_Q q0,q1,q2,q3,q4,q5; }
gate gate_Q_134450613178048 q0,q1,q2,q3,q4,q5 { gate_Q q0,q1,q2,q3,q4,q5; }
qreg q[5];
qreg flag[1];
creg meas[6];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
x flag[0];
gate_Q_134450616300752 q[0],q[1],q[2],q[3],q[4],flag[0];
gate_Q_134450616300704 q[0],q[1],q[2],q[3],q[4],flag[0];
gate_Q_134450612562992 q[0],q[1],q[2],q[3],q[4],flag[0];
gate_Q_134450613178048 q[0],q[1],q[2],q[3],q[4],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure flag[0] -> meas[5];