// InGame Studio - Azure Container Apps deployment.
//
// One container app (FastAPI backend + built React frontend), a registry for the image,
// and a Log Analytics workspace. The app keeps the match and the narrative cache in memory,
// so it runs as a single replica (see maxReplicas).
//
// Deploy in two steps: (1) this template with the placeholder image creates the registry and
// the app; (2) build and push the image to the registry, then point the app at it
// (the GitHub Actions workflow does both, see .github/workflows/deploy-azure.yml).

@description('The location for all deployed Azure resources.')
param location string = resourceGroup().location

@description('Deployment environment name prefix.')
param environmentName string = 'ingame-prod'

@description('The container image to deploy. The placeholder is replaced by the pushed image.')
param containerImage string = 'mcr.microsoft.com/azuredocs/aci-helloworld:latest'

@description('Target port exposed by the container application.')
param targetPort int = 8000

@description('CPU cores allocated to the container app.')
param cpuCore string = '1.0'

@description('Memory allocated to the container app.')
param memorySize string = '2.0Gi'

@description('Azure AI Foundry endpoint, for example https://<resource>.services.ai.azure.com. Leave empty to run on the local engine.')
param foundryEndpoint string = ''

@description('Name of the model deployment in Azure AI Foundry.')
param foundryDeployment string = 'gpt-4.1-mini'

@description('Azure AI Foundry API version.')
param foundryApiVersion string = '2024-10-21'

@secure()
@description('Azure AI Foundry API key. Stored as a Container Apps secret, never in the image.')
param foundryApiKey string = ''

@description('Azure Cosmos DB endpoint for the shared narrative store, for example https://<account>.documents.azure.com:443/. Leave empty to use the bundled file only.')
param cosmosEndpoint string = ''

@secure()
@description('Azure Cosmos DB key. Stored as a Container Apps secret.')
param cosmosKey string = ''

@secure()
@description('Key required in the X-API-Key header to post events to /api/ingest and /api/events. Leave empty to keep them open.')
param ingestApiKey string = ''

var uniqueSuffix = uniqueString(resourceGroup().id)
var acrName = 'acr${replace(environmentName, '-', '')}${take(uniqueSuffix, 6)}'
var logWorkspaceName = 'log-${environmentName}-${uniqueSuffix}'
var appEnvName = 'cae-${environmentName}-${uniqueSuffix}'
var containerAppName = 'app-ingame-${uniqueSuffix}'
var useFoundry = !empty(foundryEndpoint) && !empty(foundryApiKey)
var useCosmos = !empty(cosmosEndpoint) && !empty(cosmosKey)
var useIngestKey = !empty(ingestApiKey)

// 1. Log Analytics workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// 2. Azure Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// 3. Container Apps managed environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: appEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// 4. The container app
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: concat([
        {
          name: 'acr-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ], useFoundry ? [
        {
          name: 'foundry-api-key'
          value: foundryApiKey
        }
      ] : [], useCosmos ? [
        {
          name: 'cosmos-key'
          value: cosmosKey
        }
      ] : [], useIngestKey ? [
        {
          name: 'ingest-api-key'
          value: ingestApiKey
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'ingame-studio-engine'
          image: containerImage
          resources: {
            cpu: json(cpuCore)
            memory: memorySize
          }
          env: concat([
            {
              name: 'PORT'
              value: string(targetPort)
            }
            {
              name: 'STREAM_FPS'
              value: '25'
            }
          ], useFoundry ? [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: foundryEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: foundryDeployment
            }
            {
              name: 'AZURE_OPENAI_API_VERSION'
              value: foundryApiVersion
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'foundry-api-key'
            }
          ] : [], useCosmos ? [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
          ] : [], useIngestKey ? [
            {
              name: 'INGAME_API_KEY'
              secretRef: 'ingest-api-key'
            }
          ] : [])
        }
      ]
      scale: {
        // The narrative cache is shared through Cosmos DB. Each viewer's match is held in memory on one
        // instance, and one CPU core runs about 100 viewer-times-playback-speed units of simulation
        // (for example 30 viewers at normal speed). To scale out, add replicas AND turn on sticky sessions
        // in the ingress so each viewer keeps reaching the instance that holds their match.
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output acrLoginServer string = containerRegistry.properties.loginServer
output acrName string = containerRegistry.name
