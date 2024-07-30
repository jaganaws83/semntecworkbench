﻿// Copyright (c) Microsoft. All rights reserved.

using Azure;
using Azure.AI.ContentSafety;
using Azure.Identity;
using Microsoft.SemanticKernel;
using Microsoft.SemanticWorkbench.Connector;

namespace AgentExample02;

internal static class Program
{
    private const string CORSPolicyName = "MY-CORS";

    internal static async Task Main(string[] args)
    {
        // Setup
        var appBuilder = WebApplication.CreateBuilder(args);

        // Load settings from files and env vars
        appBuilder.Configuration
            .AddJsonFile("appsettings.json")
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddEnvironmentVariables();

        // Storage layer to persist agents configuration and conversations
        appBuilder.Services.AddSingleton<IAgentServiceStorage, AgentServiceStorage>();

        // Agent service to support multiple agent instances
        appBuilder.Services.AddSingleton<WorkbenchConnector, MyWorkbenchConnector>();

        // Azure AI Content Safety, used for demo
        var azureContentSafetyAuthType = appBuilder.Configuration.GetSection("AzureContentSafety").GetValue<string>("AuthType");
        var azureContentSafetyEndpoint = appBuilder.Configuration.GetSection("AzureContentSafety").GetValue<string>("Endpoint");
        var azureContentSafetyApiKey = appBuilder.Configuration.GetSection("AzureContentSafety").GetValue<string>("ApiKey");
        appBuilder.Services.AddSingleton<ContentSafetyClient>(_ => azureContentSafetyAuthType == "AzureIdentity"
            ? new ContentSafetyClient(new Uri(azureContentSafetyEndpoint!), new DefaultAzureCredential())
            : new ContentSafetyClient(new Uri(azureContentSafetyEndpoint!), new AzureKeyCredential(azureContentSafetyApiKey!)));

        // Misc
        appBuilder.Services.AddLogging()
            .AddCors(opt => opt.AddPolicy(CORSPolicyName, pol => pol.WithMethods("GET", "POST", "PUT", "DELETE")));

        // Build
        WebApplication app = appBuilder.Build();
        app.UseCors(CORSPolicyName);

        // Connect to workbench backend, keep alive, and accept incoming requests
        var connectorEndpoint = app.Configuration.GetSection("Workbench").Get<WorkbenchConfig>()!.ConnectorEndpoint;
        using var agentService = app.UseAgentWebservice(connectorEndpoint, true);
        await agentService.ConnectAsync().ConfigureAwait(false);

        // Start app and webservice
        await app.RunAsync().ConfigureAwait(false);
    }
}
