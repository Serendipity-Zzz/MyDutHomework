Procedure SimBatch;
Var Doc : IServerDocument;
Begin
    Doc := Client.OpenDocument('NSX', ExtractFilePath(GetWorkspace.DM_FocusedProject.DM_ProjectFullPath) + 'Pot_OperatingPoints.nsx');
    Client.ShowDocument(Doc);
    ResetParameters;
    RunProcess('SIM:RunSimulator');
    Doc := Client.GetCurrentView.OwnerDocument;
    Doc.DoFileSave('');
End;
