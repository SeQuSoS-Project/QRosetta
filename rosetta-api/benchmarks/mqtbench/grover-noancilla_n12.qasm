OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450572234720 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572296656 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572234912 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572244080 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572237024 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572242640 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572236640 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572234096 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572236736 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572297232 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572236832 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572244992 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572238944 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572298384 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572238560 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572299248 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572238656 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572300496 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572238752 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572300880 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572238176 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572301120 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572239712 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572238464 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450572239808 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572300160 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572239904 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572302752 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450572233424 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572303760 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450572235440 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572305344 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450572234336 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572304000 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450572234240 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572306016 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450572241104 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572307504 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450572240768 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572308704 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450572240864 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572309088 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450572240960 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572306592 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450572242592 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572311104 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450572311872 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450572242352 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572559232 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450574719120 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450572312400 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450572308320 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450572560048 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450572560096 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450572561056 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450572561728 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450572561152 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450572312112 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450572562928 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450572560576 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450572563504 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450572558992 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary q11; mcx_vchain_134450572234720 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572296656 q11; mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary q11; mcx_vchain_134450572234912 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572244080 q11; mcx_vchain_134450572237024 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450572242640 q10; mcx_vchain_134450572236640 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572234096 q10; mcx_vchain_134450572236736 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450572297232 q10; mcx_vchain_134450572236832 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572244992 q10; mcx_vchain_134450572238944 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572298384 q9; mcx_vchain_134450572238560 q5,q6,q7,q8,q9,q3,q4; unitary_134450572299248 q9; mcx_vchain_134450572238656 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572300496 q9; mcx_vchain_134450572238752 q5,q6,q7,q8,q9,q3,q4; unitary_134450572300880 q9; mcx_vchain_134450572238176 q0,q1,q2,q3,q8,q4,q5; unitary_134450572301120 q8; mcx_vchain_134450572239712 q4,q5,q6,q7,q8,q2,q3; unitary_134450572238464 q8; mcx_vchain_134450572239808 q0,q1,q2,q3,q8,q4,q5; unitary_134450572300160 q8; mcx_vchain_134450572239904 q4,q5,q6,q7,q8,q2,q3; unitary_134450572302752 q8; mcx_vchain_134450572233424 q0,q1,q2,q3,q7,q4,q5; unitary_134450572303760 q7; mcx_vchain_134450572235440 q4,q5,q6,q7,q3; unitary_134450572305344 q7; mcx_vchain_134450572234336 q0,q1,q2,q3,q7,q4,q5; unitary_134450572304000 q7; mcx_vchain_134450572234240 q4,q5,q6,q7,q3; unitary_134450572306016 q7; mcx_vchain_134450572241104 q0,q1,q2,q6,q3; unitary_134450572307504 q6; mcx_vchain_134450572240768 q3,q4,q5,q6,q2; unitary_134450572308704 q6; mcx_vchain_134450572240864 q0,q1,q2,q6,q3; unitary_134450572309088 q6; mcx_vchain_134450572240960 q3,q4,q5,q6,q2; unitary_134450572306592 q6; mcx_vchain_134450572242592 q0,q1,q2,q5,q3; unitary_134450572311104 q5; ccx q3,q4,q5; unitary_134450572311872 q5; mcx_vchain_134450572242352 q0,q1,q2,q5,q3; unitary_134450572559232 q5; ccx q3,q4,q5; unitary_134450574719120 q5; ccx q0,q1,q4; unitary_134450572312400 q4; ccx q2,q3,q4; unitary_134450572308320 q4; ccx q0,q1,q4; unitary_134450572560048 q4; ccx q2,q3,q4; unitary_134450572560096 q4; ccx q0,q1,q3; unitary_134450572561056 q3; cx q2,q3; unitary_134450572561728 q3; ccx q0,q1,q3; unitary_134450572561152 q3; cx q2,q3; unitary_134450572312112 q3; cx q0,q2; unitary_134450572562928 q2; cx q1,q2; unitary_134450572560576 q2; cx q0,q2; unitary_134450572563504 q2; cx q1,q2; unitary_134450572558992 q2; crz(pi/1024) q0,q1; p(pi/2048) q0; }
gate mcx_vchain_134450572569696 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate mcx_vchain_134450572569312 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572563264 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572569408 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate mcx_vchain_134450572569504 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572563600 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572562544 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450570615536 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572568832 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450570611840 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572567632 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450570616160 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572568592 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572568544 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572571136 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572567776 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572570752 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572304720 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572570848 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572309376 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572570944 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572304960 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572573248 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572301984 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572572864 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572242688 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450572572960 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572233232 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572573056 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572233856 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450570608816 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450570613424 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450572574448 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572569216 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450572574544 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450570616928 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450572574640 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450570615152 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450570610352 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450570614432 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450570619520 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450570610112 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450570618800 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450570620144 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450570620624 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450570616832 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450570621152 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450570621968 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450570623696 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450570623408 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450570623744 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450570611936 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450570623888 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450570838384 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450570838864 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450570839632 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcphase_134450572306496(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { mcx_vchain_134450572569696 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary q10; mcx_vchain_134450572569312 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572563264 q10; mcx_vchain_134450572569408 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary q10; mcx_vchain_134450572569504 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572563600 q10; mcx_vchain_134450572562544 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450570615536 q9; mcx_vchain_134450572568832 q5,q6,q7,q8,q9,q3,q4; unitary_134450570611840 q9; mcx_vchain_134450572567632 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450570616160 q9; mcx_vchain_134450572568592 q5,q6,q7,q8,q9,q3,q4; unitary_134450572568544 q9; mcx_vchain_134450572571136 q0,q1,q2,q3,q8,q4,q5; unitary_134450572567776 q8; mcx_vchain_134450572570752 q4,q5,q6,q7,q8,q2,q3; unitary_134450572304720 q8; mcx_vchain_134450572570848 q0,q1,q2,q3,q8,q4,q5; unitary_134450572309376 q8; mcx_vchain_134450572570944 q4,q5,q6,q7,q8,q2,q3; unitary_134450572304960 q8; mcx_vchain_134450572573248 q0,q1,q2,q3,q7,q4,q5; unitary_134450572301984 q7; mcx_vchain_134450572572864 q4,q5,q6,q7,q3; unitary_134450572242688 q7; mcx_vchain_134450572572960 q0,q1,q2,q3,q7,q4,q5; unitary_134450572233232 q7; mcx_vchain_134450572573056 q4,q5,q6,q7,q3; unitary_134450572233856 q7; mcx_vchain_134450570608816 q0,q1,q2,q6,q3; unitary_134450570613424 q6; mcx_vchain_134450572574448 q3,q4,q5,q6,q2; unitary_134450572569216 q6; mcx_vchain_134450572574544 q0,q1,q2,q6,q3; unitary_134450570616928 q6; mcx_vchain_134450572574640 q3,q4,q5,q6,q2; unitary_134450570615152 q6; mcx_vchain_134450570610352 q0,q1,q2,q5,q3; unitary_134450570614432 q5; ccx q3,q4,q5; unitary_134450570619520 q5; mcx_vchain_134450570610112 q0,q1,q2,q5,q3; unitary_134450570618800 q5; ccx q3,q4,q5; unitary_134450570620144 q5; ccx q0,q1,q4; unitary_134450570620624 q4; ccx q2,q3,q4; unitary_134450570616832 q4; ccx q0,q1,q4; unitary_134450570621152 q4; ccx q2,q3,q4; unitary_134450570621968 q4; ccx q0,q1,q3; unitary_134450570623696 q3; cx q2,q3; unitary_134450570623408 q3; ccx q0,q1,q3; unitary_134450570623744 q3; cx q2,q3; unitary_134450570611936 q3; cx q0,q2; unitary_134450570623888 q2; cx q1,q2; unitary_134450570838384 q2; cx q0,q2; unitary_134450570838864 q2; cx q1,q2; unitary_134450570839632 q2; crz(pi/512) q0,q1; p(pi/1024) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { h q10; mcphase_134450572306496(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; h q10; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; h q10; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; h q10; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; }
gate gate_Q_134450571803872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572305632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572245952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572566000 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570613232 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450574720848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570839728 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570840832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570844864 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570844384 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570848464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570851104 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570852928 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570851632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450571804208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570851776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570846256 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570849856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450570612608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572560624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572237600 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450571789664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573617360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573621440 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573614528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573610688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573289536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573293376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573283536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573057472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573054544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572928176 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450573056320 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572766352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
gate gate_Q_134450572924336 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; }
qreg q[11];
qreg flag[1];
creg meas[12];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
h q[8];
h q[9];
h q[10];
x flag[0];
gate_Q_134450571803872 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572305632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572245952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572566000 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570613232 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450574720848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570839728 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570840832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570844864 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570844384 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570848464 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570851104 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570852928 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570851632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450571804208 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570851776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570846256 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570849856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450570612608 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572560624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572237600 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450571789664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573617360 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573621440 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573614528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573610688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573289536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573293376 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573283536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573057472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573054544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572928176 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450573056320 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572766352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
gate_Q_134450572924336 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure q[8] -> meas[8];
measure q[9] -> meas[9];
measure q[10] -> meas[10];
measure flag[0] -> meas[11];