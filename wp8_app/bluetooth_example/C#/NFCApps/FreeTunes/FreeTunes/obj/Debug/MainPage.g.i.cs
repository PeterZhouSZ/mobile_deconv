﻿#pragma checksum "C:\Users\timlav\Desktop\BUILD DEMOS\NFCApps\FreeTunes\FreeTunes\MainPage.xaml" "{406ea660-64cf-4c82-b6f0-42d48172a799}" "BCD998D3C27BD688F02636A5A8B10290"
//------------------------------------------------------------------------------
// <auto-generated>
//     This code was generated by a tool.
//     Runtime Version:4.0.30319.18010
//
//     Changes to this file may cause incorrect behavior and will be lost if
//     the code is regenerated.
// </auto-generated>
//------------------------------------------------------------------------------

using Microsoft.Phone.Controls;
using System;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Automation.Provider;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Ink;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Resources;
using System.Windows.Shapes;
using System.Windows.Threading;


namespace FreeTunes {
    
    
    public partial class MainPage : Microsoft.Phone.Controls.PhoneApplicationPage {
        
        internal System.Windows.Controls.Grid LayoutRoot;
        
        internal System.Windows.Controls.StackPanel TitlePanel;
        
        internal System.Windows.Controls.Grid ContentPanel;
        
        internal System.Windows.Controls.ProgressBar MyProgressBar;
        
        internal System.Windows.Controls.TextBox UriTextBox;
        
        internal System.Windows.Controls.TextBox ArtistTextBox;
        
        internal System.Windows.Controls.TextBox SongTitleTextBox;
        
        internal System.Windows.Controls.Button DownloadSongButton;
        
        internal System.Windows.Controls.Button PlaySongButton;
        
        internal System.Windows.Controls.Button ConnectToPeer;
        
        internal System.Windows.Controls.TextBlock StatusTextBlock;
        
        internal System.Windows.Controls.ProgressBar DownloadProgressBar;
        
        internal System.Windows.Controls.MediaElement MyMedia;
        
        private bool _contentLoaded;
        
        /// <summary>
        /// InitializeComponent
        /// </summary>
        [System.Diagnostics.DebuggerNonUserCodeAttribute()]
        public void InitializeComponent() {
            if (_contentLoaded) {
                return;
            }
            _contentLoaded = true;
            System.Windows.Application.LoadComponent(this, new System.Uri("/FreeTunes;component/MainPage.xaml", System.UriKind.Relative));
            this.LayoutRoot = ((System.Windows.Controls.Grid)(this.FindName("LayoutRoot")));
            this.TitlePanel = ((System.Windows.Controls.StackPanel)(this.FindName("TitlePanel")));
            this.ContentPanel = ((System.Windows.Controls.Grid)(this.FindName("ContentPanel")));
            this.MyProgressBar = ((System.Windows.Controls.ProgressBar)(this.FindName("MyProgressBar")));
            this.UriTextBox = ((System.Windows.Controls.TextBox)(this.FindName("UriTextBox")));
            this.ArtistTextBox = ((System.Windows.Controls.TextBox)(this.FindName("ArtistTextBox")));
            this.SongTitleTextBox = ((System.Windows.Controls.TextBox)(this.FindName("SongTitleTextBox")));
            this.DownloadSongButton = ((System.Windows.Controls.Button)(this.FindName("DownloadSongButton")));
            this.PlaySongButton = ((System.Windows.Controls.Button)(this.FindName("PlaySongButton")));
            this.ConnectToPeer = ((System.Windows.Controls.Button)(this.FindName("ConnectToPeer")));
            this.StatusTextBlock = ((System.Windows.Controls.TextBlock)(this.FindName("StatusTextBlock")));
            this.DownloadProgressBar = ((System.Windows.Controls.ProgressBar)(this.FindName("DownloadProgressBar")));
            this.MyMedia = ((System.Windows.Controls.MediaElement)(this.FindName("MyMedia")));
        }
    }
}

