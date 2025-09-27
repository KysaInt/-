using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;

namespace AYE
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();
        }

        private void Module1_Click(object sender, RoutedEventArgs e)
        {
            Module1 module1 = new Module1();
            module1.Execute();
            MessageBox.Show("Module 1 executed");
        }

        private void Module2_Click(object sender, RoutedEventArgs e)
        {
            Module2 module2 = new Module2();
            module2.Execute();
            MessageBox.Show("Module 2 executed");
        }

        private void Module3_Click(object sender, RoutedEventArgs e)
        {
            Module3 module3 = new Module3();
            module3.Execute();
            MessageBox.Show("Module 3 executed");
        }
    }
}