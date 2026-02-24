## Fast Track Deployment of only Rosetta API:

docker build -f ./rosetta-api/Dockerfile -t image-registry.apps.2.rahti.csc.fi/qrosetta/rosetta-api:latest .
docker push image-registry.apps.2.rahti.csc.fi/qrosetta/rosetta-api:latest
oc delete pods -l app=rosetta-api -n qrosetta


## Fast Track Deployment of only Rosetta UI:
