## Fast Track Deployment of only Rosetta API:

docker build -f ./rosetta-api/Dockerfile -t image-registry.apps.2.rahti.csc.fi/qrosetta/rosetta-api:latest .
docker push image-registry.apps.2.rahti.csc.fi/qrosetta/rosetta-api:latest
oc delete pods -l app=rosetta-api -n qrosetta


## Fast Track Deployment of only Rosetta UI:


## LOGINS OC AND DOCKER:
oc login --token=sha256~VZ5pqA2bYzaNX9nh7n5eM87-1oC2NBfROmYYsUN_2p0 --server=https://api.2.rahti.csc.fi:6443
docker login -u $(oc whoami) -p sha256~VZ5pqA2bYzaNX9nh7n5eM87-1oC2NBfROmYYsUN_2p0 image-registry.apps.2.rahti.csc.fi