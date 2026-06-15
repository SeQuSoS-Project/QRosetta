OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450609226384 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609228304 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450609230272 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609226576 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450609233968 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609229648 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450609231952 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609230992 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450609234496 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609230752 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450609238144 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609231184 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450609238432 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450609241216 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450609239248 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610144512 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450609239152 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610143312 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450609238960 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610145664 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450609236368 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610146768 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450609232816 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610148592 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450609232144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610149984 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450609233680 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610641840 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450609225904 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610144464 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610145904 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450609226864 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610152432 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610147392 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450610153872 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450609240256 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450610153920 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450610151136 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450610147824 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450610155264 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450610155600 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450610153056 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450610157280 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450610156368 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450610156512 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450610156704 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450609226384 q5,q6,q7,q8,q9,q3,q4; unitary_134450609228304 q9; mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450609230272 q5,q6,q7,q8,q9,q3,q4; unitary_134450609226576 q9; mcx_vchain_134450609233968 q0,q1,q2,q3,q8,q4,q5; unitary_134450609229648 q8; mcx_vchain_134450609231952 q4,q5,q6,q7,q8,q2,q3; unitary_134450609230992 q8; mcx_vchain_134450609234496 q0,q1,q2,q3,q8,q4,q5; unitary_134450609230752 q8; mcx_vchain_134450609238144 q4,q5,q6,q7,q8,q2,q3; unitary_134450609231184 q8; mcx_vchain_134450609238432 q0,q1,q2,q3,q7,q4,q5; unitary_134450609241216 q7; mcx_vchain_134450609239248 q4,q5,q6,q7,q3; unitary_134450610144512 q7; mcx_vchain_134450609239152 q0,q1,q2,q3,q7,q4,q5; unitary_134450610143312 q7; mcx_vchain_134450609238960 q4,q5,q6,q7,q3; unitary_134450610145664 q7; mcx_vchain_134450609236368 q0,q1,q2,q6,q3; unitary_134450610146768 q6; mcx_vchain_134450609232816 q3,q4,q5,q6,q2; unitary_134450610148592 q6; mcx_vchain_134450609232144 q0,q1,q2,q6,q3; unitary_134450610149984 q6; mcx_vchain_134450609233680 q3,q4,q5,q6,q2; unitary_134450610641840 q6; mcx_vchain_134450609225904 q0,q1,q2,q5,q3; unitary_134450610144464 q5; ccx q3,q4,q5; unitary_134450610145904 q5; mcx_vchain_134450609226864 q0,q1,q2,q5,q3; unitary_134450610152432 q5; ccx q3,q4,q5; unitary_134450610147392 q5; ccx q0,q1,q4; unitary_134450610153872 q4; ccx q2,q3,q4; unitary_134450609240256 q4; ccx q0,q1,q4; unitary_134450610153920 q4; ccx q2,q3,q4; unitary_134450610151136 q4; ccx q0,q1,q3; unitary_134450610147824 q3; cx q2,q3; unitary_134450610155264 q3; ccx q0,q1,q3; unitary_134450610155600 q3; cx q2,q3; unitary_134450610153056 q3; cx q0,q2; unitary_134450610157280 q2; cx q1,q2; unitary_134450610156368 q2; cx q0,q2; unitary_134450610156512 q2; cx q1,q2; unitary_134450610156704 q2; crz(pi/256) q0,q1; p(pi/512) q0; }
gate mcx_vchain_134450573821616 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate mcx_vchain_134450573821232 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573828576 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450573821328 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate mcx_vchain_134450573821424 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573829632 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450573823104 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610157472 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450573822720 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573826368 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450573822816 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573823056 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450573822912 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573832896 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450573824352 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573834144 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450573823968 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610147488 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450573824064 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450609231760 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450573824160 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610984992 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450609227008 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573824976 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450573823824 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610985760 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573821184 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450573825840 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450573832848 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450573820464 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450573820368 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450573835680 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450574033216 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450573832272 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450609229168 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450574033600 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450574034320 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450574033360 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450574035760 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450574036240 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcphase_134450610153824(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8 { mcx_vchain_134450573821616 q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain_134450573821232 q4,q5,q6,q7,q8,q2,q3; unitary_134450573828576 q8; mcx_vchain_134450573821328 q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain_134450573821424 q4,q5,q6,q7,q8,q2,q3; unitary_134450573829632 q8; mcx_vchain_134450573823104 q0,q1,q2,q3,q7,q4,q5; unitary_134450610157472 q7; mcx_vchain_134450573822720 q4,q5,q6,q7,q3; unitary_134450573826368 q7; mcx_vchain_134450573822816 q0,q1,q2,q3,q7,q4,q5; unitary_134450573823056 q7; mcx_vchain_134450573822912 q4,q5,q6,q7,q3; unitary_134450573832896 q7; mcx_vchain_134450573824352 q0,q1,q2,q6,q3; unitary_134450573834144 q6; mcx_vchain_134450573823968 q3,q4,q5,q6,q2; unitary_134450610147488 q6; mcx_vchain_134450573824064 q0,q1,q2,q6,q3; unitary_134450609231760 q6; mcx_vchain_134450573824160 q3,q4,q5,q6,q2; unitary_134450610984992 q6; mcx_vchain_134450609227008 q0,q1,q2,q5,q3; unitary_134450573824976 q5; ccx q3,q4,q5; unitary_134450573823824 q5; mcx_vchain_134450610985760 q0,q1,q2,q5,q3; unitary_134450573821184 q5; ccx q3,q4,q5; unitary_134450573825840 q5; ccx q0,q1,q4; unitary_134450573832848 q4; ccx q2,q3,q4; unitary_134450573820464 q4; ccx q0,q1,q4; unitary_134450573820368 q4; ccx q2,q3,q4; unitary_134450573835680 q4; ccx q0,q1,q3; unitary_134450574033216 q3; cx q2,q3; unitary_134450573832272 q3; ccx q0,q1,q3; unitary_134450609229168 q3; cx q2,q3; unitary_134450574033600 q3; cx q0,q2; unitary_134450574034320 q2; cx q1,q2; unitary_134450574033360 q2; cx q0,q2; unitary_134450574035760 q2; cx q1,q2; unitary_134450574036240 q2; crz(pi/128) q0,q1; p(pi/256) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8 { h q8; mcphase_134450610153824(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8; h q8; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; h q8; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8; h q8; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; }
gate gate_Q_134450612310800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450609230416 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450612720592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450573824496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450612723280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450573833040 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574039888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574040656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574043296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574038688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574046080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574043248 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574048144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574313520 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574315104 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574317168 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
gate gate_Q_134450574318272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; }
qreg q[9];
qreg flag[1];
creg meas[10];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
h q[8];
x flag[0];
gate_Q_134450612310800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450609230416 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450612720592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450573824496 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450612723280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450573833040 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574039888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574040656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574043296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574038688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574046080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574043248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574048144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574313520 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574315104 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574317168 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
gate_Q_134450574318272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure q[8] -> meas[8];
measure flag[0] -> meas[9];